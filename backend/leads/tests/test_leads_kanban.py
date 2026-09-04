import datetime

import pytest
from django.db import connection
from django.utils import timezone

from communications.models import (
    EmailDraft,
    EmailThread,
    LeadEmailMessage,
    MailboxConnection,
)
from leads.email_activity import LeadEmailDirection, LeadEmailStatus
from leads.models import Lead, LeadPipeline, LeadStage
from leads.serializer import LeadKanbanCardSerializer

pg_only = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="JSONField contains lookup requires PostgreSQL",
)


def _set_rls(org):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_org', %s, false)", [str(org.id)]
        )


@pytest.fixture
def lead_email_factory(admin_user):
    """Create leads with concise, deterministic email histories."""
    sequence = iter(range(1, 1000))
    mailboxes = {}

    def create(
        *,
        org,
        name,
        draft_count=0,
        directions=(),
        next_follow_up=None,
    ):
        _set_rls(org)
        item_number = next(sequence)
        mailbox = mailboxes.get(org.id)
        if mailbox is None:
            mailbox = MailboxConnection.objects.create(
                org=org,
                email_address=f"kanban-{org.id}@bruensdt.nl",
                credentials_encrypted="test",
            )
            mailboxes[org.id] = mailbox

        lead = Lead.objects.create(
            company_name=name,
            email=f"lead-{item_number}@example.com",
            status="assigned",
            next_follow_up=next_follow_up,
            created_by=admin_user,
            org=org,
        )
        for draft_number in range(draft_count):
            EmailDraft.objects.create(
                org=org,
                lead=lead,
                mailbox=mailbox,
                recipient=lead.email,
                subject=f"Draft {draft_number + 1}",
                body_text="Draft body",
            )

        if directions:
            base_time = timezone.now() - datetime.timedelta(minutes=len(directions))
            thread = EmailThread.objects.create(
                org=org,
                mailbox=mailbox,
                lead=lead,
                provider_thread_id=f"thread-{item_number}",
                subject=name,
                last_message_at=base_time,
            )
            for message_number, direction in enumerate(directions):
                occurred_at = base_time + datetime.timedelta(minutes=message_number)
                LeadEmailMessage.objects.create(
                    org=org,
                    thread=thread,
                    mailbox=mailbox,
                    provider_message_id=f"message-{item_number}-{message_number}",
                    direction=direction,
                    from_address=(
                        lead.email
                        if direction == LeadEmailDirection.INBOUND
                        else mailbox.email_address
                    ),
                    to_addresses=[
                        mailbox.email_address
                        if direction == LeadEmailDirection.INBOUND
                        else lead.email
                    ],
                    subject=name,
                    occurred_at=occurred_at,
                )
            thread.last_message_at = occurred_at
            thread.save(update_fields=["last_message_at"])

        return lead

    return create


def _activity_for_status(email_status):
    if email_status == LeadEmailStatus.DRAFT:
        return {"draft_count": 1}
    if email_status == LeadEmailStatus.SENT:
        return {"directions": [LeadEmailDirection.OUTBOUND]}
    if email_status == LeadEmailStatus.REPLIED:
        return {
            "directions": [
                LeadEmailDirection.OUTBOUND,
                LeadEmailDirection.INBOUND,
            ]
        }
    if email_status == LeadEmailStatus.FOLLOW_UP:
        return {
            "directions": [LeadEmailDirection.OUTBOUND],
            "next_follow_up": timezone.localdate() - datetime.timedelta(days=1),
        }
    return {}


def _response_leads(response, endpoint):
    payload = response.json()
    if endpoint == "/api/leads/kanban/":
        return [lead for column in payload["columns"] for lead in column["leads"]]
    return payload["open_leads"]["open_leads"]


@pytest.mark.django_db
class TestLeadPipelineListCreateView:
    """Tests for GET/POST /api/leads/pipelines/."""

    def test_create_pipeline(self, admin_client, org_a):
        response = admin_client.post(
            "/api/leads/pipelines/",
            {"name": "Sales Pipeline"},
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Sales Pipeline"
        assert LeadPipeline.objects.filter(
            name="Sales Pipeline", org=org_a
        ).exists()

    def test_list_pipelines(self, admin_client, admin_user, org_a):
        LeadPipeline.objects.create(
            name="Pipeline A", org=org_a, created_by=admin_user
        )
        response = admin_client.get("/api/leads/pipelines/")
        assert response.status_code == 200
        data = response.json()
        assert "pipelines" in data

    def test_create_pipeline_non_admin(self, user_client):
        response = user_client.post(
            "/api/leads/pipelines/",
            {"name": "Blocked Pipeline"},
            format="json",
        )
        assert response.status_code == 403

    def test_create_pipeline_with_default_stages(self, admin_client, org_a):
        """Creating a pipeline with create_default_stages=True adds 6 stages."""
        response = admin_client.post(
            "/api/leads/pipelines/",
            {"name": "Default Stages Pipeline", "create_default_stages": True},
            format="json",
        )
        assert response.status_code == 201
        pipeline = LeadPipeline.objects.get(name="Default Stages Pipeline")
        assert pipeline.stages.count() == 6

    def test_create_pipeline_without_default_stages(self, admin_client, org_a):
        """Creating a pipeline with create_default_stages=False adds no stages."""
        response = admin_client.post(
            "/api/leads/pipelines/",
            {"name": "No Stages Pipeline", "create_default_stages": False},
            format="json",
        )
        assert response.status_code == 201
        pipeline = LeadPipeline.objects.get(name="No Stages Pipeline")
        assert pipeline.stages.count() == 0

    def test_create_pipeline_invalid_data(self, admin_client, org_a):
        """Creating a pipeline with missing name returns 400."""
        response = admin_client.post(
            "/api/leads/pipelines/",
            {},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestLeadPipelineDetailView:
    """Tests for GET/PUT/DELETE /api/leads/pipelines/<pk>/."""

    def test_get_pipeline_detail(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Detail Pipeline", org=org_a, created_by=admin_user
        )
        response = admin_client.get(f"/api/leads/pipelines/{pipeline.id}/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Detail Pipeline"

    def test_update_pipeline(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Old Name", org=org_a, created_by=admin_user
        )
        response = admin_client.put(
            f"/api/leads/pipelines/{pipeline.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"

    def test_delete_empty_pipeline(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Empty Pipeline", org=org_a, created_by=admin_user
        )
        response = admin_client.delete(
            f"/api/leads/pipelines/{pipeline.id}/"
        )
        assert response.status_code == 204

    def test_delete_pipeline_with_leads_fails(self, admin_client, admin_user, org_a):
        """Cannot delete a pipeline that has leads associated via stages."""
        _set_rls(org_a)
        pipeline = LeadPipeline.objects.create(
            name="Busy Pipeline", org=org_a, created_by=admin_user
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline, name="Active", order=0, org=org_a
        )
        Lead.objects.create(
            first_name="Busy",
            last_name="Lead",
            email="busylead@example.com",
            created_by=admin_user,
            org=org_a,
            stage=stage,
        )
        response = admin_client.delete(f"/api/leads/pipelines/{pipeline.id}/")
        assert response.status_code == 400

    def test_update_pipeline_non_admin_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin user cannot update a pipeline."""
        pipeline = LeadPipeline.objects.create(
            name="No Touch", org=org_a, created_by=admin_user
        )
        response = user_client.put(
            f"/api/leads/pipelines/{pipeline.id}/",
            {"name": "Hacked"},
            format="json",
        )
        assert response.status_code == 403

    def test_delete_pipeline_non_admin_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin user cannot delete a pipeline."""
        pipeline = LeadPipeline.objects.create(
            name="Protected Pipeline", org=org_a, created_by=admin_user
        )
        response = user_client.delete(f"/api/leads/pipelines/{pipeline.id}/")
        assert response.status_code == 403

    def test_update_pipeline_invalid_data(self, admin_client, admin_user, org_a):
        """PUT with invalid data returns 400."""
        pipeline = LeadPipeline.objects.create(
            name="Valid Name", org=org_a, created_by=admin_user
        )
        # Sending an empty name should fail
        response = admin_client.put(
            f"/api/leads/pipelines/{pipeline.id}/",
            {"name": ""},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestLeadStageViews:
    """Tests for stage creation, update, delete, and reorder."""

    def test_create_stage(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Stage Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        response = admin_client.post(
            f"/api/leads/pipelines/{pipeline.id}/stages/",
            {
                "name": "Qualification",
                "order": 1,
                "color": "#FF5733",
                "stage_type": "open",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Qualification"

    def test_update_stage(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Update Stage Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline,
            name="Initial",
            order=0,
            color="#000000",
            stage_type="open",
            org=org_a,
        )
        response = admin_client.put(
            f"/api/leads/stages/{stage.id}/",
            {"name": "Renamed Stage", "color": "#FFFFFF"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed Stage"

    def test_delete_empty_stage(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Delete Stage Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline,
            name="Disposable",
            order=0,
            color="#000000",
            stage_type="open",
            org=org_a,
        )
        response = admin_client.delete(f"/api/leads/stages/{stage.id}/")
        assert response.status_code == 204

    def test_reorder_stages(self, admin_client, admin_user, org_a):
        pipeline = LeadPipeline.objects.create(
            name="Reorder Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        stage_a = LeadStage.objects.create(
            pipeline=pipeline,
            name="Stage A",
            order=0,
            org=org_a,
        )
        stage_b = LeadStage.objects.create(
            pipeline=pipeline,
            name="Stage B",
            order=1,
            org=org_a,
        )
        # Reverse the order
        response = admin_client.post(
            f"/api/leads/pipelines/{pipeline.id}/stages/reorder/",
            {"stage_ids": [str(stage_b.id), str(stage_a.id)]},
            format="json",
        )
        assert response.status_code == 200
        stage_a.refresh_from_db()
        stage_b.refresh_from_db()
        assert stage_b.order < stage_a.order

    def test_delete_stage_with_leads_fails(self, admin_client, admin_user, org_a):
        """Cannot delete a stage that has leads attached."""
        _set_rls(org_a)
        pipeline = LeadPipeline.objects.create(
            name="Stage With Leads Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline, name="Busy Stage", order=0, org=org_a
        )
        Lead.objects.create(
            first_name="Staged",
            last_name="Lead",
            email="stagedlead@example.com",
            created_by=admin_user,
            org=org_a,
            stage=stage,
        )
        response = admin_client.delete(f"/api/leads/stages/{stage.id}/")
        assert response.status_code == 400

    def test_create_stage_non_admin_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin user cannot create a stage."""
        pipeline = LeadPipeline.objects.create(
            name="Admin Only Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        response = user_client.post(
            f"/api/leads/pipelines/{pipeline.id}/stages/",
            {"name": "Blocked", "order": 1},
            format="json",
        )
        assert response.status_code == 403

    def test_update_stage_non_admin_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin user cannot update a stage."""
        pipeline = LeadPipeline.objects.create(
            name="No Update Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline, name="No Touch", order=0, org=org_a
        )
        response = user_client.put(
            f"/api/leads/stages/{stage.id}/",
            {"name": "Hacked"},
            format="json",
        )
        assert response.status_code == 403

    def test_delete_stage_non_admin_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin user cannot delete a stage."""
        pipeline = LeadPipeline.objects.create(
            name="No Delete Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline, name="Protected", order=0, org=org_a
        )
        response = user_client.delete(f"/api/leads/stages/{stage.id}/")
        assert response.status_code == 403

    def test_create_stage_invalid_data(self, admin_client, admin_user, org_a):
        """Creating a stage with missing required fields returns 400."""
        pipeline = LeadPipeline.objects.create(
            name="Invalid Stage Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        response = admin_client.post(
            f"/api/leads/pipelines/{pipeline.id}/stages/",
            {},
            format="json",
        )
        assert response.status_code == 400

    def test_reorder_stages_invalid_ids(self, admin_client, admin_user, org_a):
        """Reorder with invalid stage IDs returns 400."""
        pipeline = LeadPipeline.objects.create(
            name="Reorder Invalid Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        LeadStage.objects.create(
            pipeline=pipeline, name="Only", order=0, org=org_a
        )
        response = admin_client.post(
            f"/api/leads/pipelines/{pipeline.id}/stages/reorder/",
            {"stage_ids": ["00000000-0000-0000-0000-000000000001"]},
            format="json",
        )
        assert response.status_code == 400

    def test_reorder_stages_non_admin_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin cannot reorder stages."""
        pipeline = LeadPipeline.objects.create(
            name="Reorder Forbidden Pipeline",
            org=org_a,
            created_by=admin_user,
        )
        response = user_client.post(
            f"/api/leads/pipelines/{pipeline.id}/stages/reorder/",
            {"stage_ids": []},
            format="json",
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestLeadKanbanView:
    """Tests for GET /api/leads/kanban/."""

    def test_kanban_view(self, admin_client, org_a):
        response = admin_client.get("/api/leads/kanban/")
        assert response.status_code == 200
        data = response.json()
        assert "columns" in data

    def test_kanban_status_mode(self, admin_client, admin_user, org_a):
        """Kanban without pipeline_id returns status-based columns."""
        _set_rls(org_a)
        Lead.objects.create(
            first_name="Kanban",
            last_name="Lead",
            email="kanban@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.get("/api/leads/kanban/")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "status"
        assert data["pipeline"] is None
        assert data["total_leads"] >= 1
        # Status columns should exist
        column_ids = [col["id"] for col in data["columns"]]
        assert "assigned" in column_ids

    def test_kanban_pipeline_mode(self, admin_client, admin_user, org_a):
        """Kanban with pipeline_id returns pipeline-based columns."""
        _set_rls(org_a)
        pipeline = LeadPipeline.objects.create(
            name="Kanban Pipeline", org=org_a, created_by=admin_user
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline, name="New", order=1, org=org_a
        )
        Lead.objects.create(
            first_name="Pipe",
            last_name="Lead",
            email="pipelead@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
            stage=stage,
        )
        response = admin_client.get(
            "/api/leads/kanban/", {"pipeline_id": str(pipeline.id)}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "pipeline"
        assert data["pipeline"] is not None
        assert len(data["columns"]) == 1
        assert data["columns"][0]["name"] == "New"

    def test_kanban_search_filter(self, admin_client, admin_user, org_a):
        """Kanban search filter works."""
        _set_rls(org_a)
        Lead.objects.create(
            first_name="Searchable",
            last_name="KanbanLead",
            email="searchkan@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.get("/api/leads/kanban/", {"search": "Searchable"})
        assert response.status_code == 200
        data = response.json()
        assert data["total_leads"] >= 1

    def test_kanban_rating_filter(self, admin_client, admin_user, org_a):
        """Kanban rating filter works."""
        _set_rls(org_a)
        Lead.objects.create(
            first_name="Hot",
            last_name="Lead",
            email="hotlead@example.com",
            status="assigned",
            rating="HOT",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.get("/api/leads/kanban/", {"rating": "HOT"})
        assert response.status_code == 200

    def test_kanban_exposes_orthogonal_email_activity(
        self, admin_client, org_a, lead_email_factory
    ):
        """Cards expose primary status plus the facts from which it is derived."""
        for email_status in LeadEmailStatus.values:
            lead_email_factory(
                org=org_a,
                name=f"Email {email_status}",
                **_activity_for_status(email_status),
            )
        lead_email_factory(
            org=org_a,
            name="Draft after send",
            draft_count=1,
            directions=[LeadEmailDirection.OUTBOUND],
        )
        lead_email_factory(
            org=org_a,
            name="Outbound after reply",
            directions=[
                LeadEmailDirection.OUTBOUND,
                LeadEmailDirection.INBOUND,
                LeadEmailDirection.OUTBOUND,
            ],
        )

        response = admin_client.get("/api/leads/kanban/")

        assert response.status_code == 200
        cards = {
            card["company_name"]: card
            for card in _response_leads(response, "/api/leads/kanban/")
        }
        for email_status in LeadEmailStatus.values:
            assert cards[f"Email {email_status}"]["email_status"] == email_status
        assert cards["Draft after send"]["email_status"] == LeadEmailStatus.DRAFT
        assert cards["Draft after send"]["email_draft_count"] == 1
        assert (
            cards["Draft after send"]["latest_email_direction"]
            == LeadEmailDirection.OUTBOUND
        )
        assert cards["Draft after send"]["email_follow_up_overdue"] is False
        assert cards["Draft after send"]["last_email_at"] is not None
        assert cards["Outbound after reply"]["email_status"] == LeadEmailStatus.SENT
        assert (
            cards["Outbound after reply"]["latest_email_direction"]
            == LeadEmailDirection.OUTBOUND
        )

    @pytest.mark.parametrize("endpoint", ["/api/leads/kanban/", "/api/leads/"])
    @pytest.mark.parametrize("email_status", LeadEmailStatus.values)
    def test_email_status_filter(
        self,
        admin_client,
        org_a,
        lead_email_factory,
        endpoint,
        email_status,
    ):
        """Every supported status filters consistently in table and kanban views."""
        expected = lead_email_factory(
            org=org_a,
            name=f"Target {email_status}",
            **_activity_for_status(email_status),
        )
        distractor_status = (
            LeadEmailStatus.SENT
            if email_status != LeadEmailStatus.SENT
            else LeadEmailStatus.DRAFT
        )
        lead_email_factory(
            org=org_a,
            name="Distractor",
            **_activity_for_status(distractor_status),
        )

        response = admin_client.get(endpoint, {"email_status": email_status})

        assert response.status_code == 200
        assert [lead["id"] for lead in _response_leads(response, endpoint)] == [
            str(expected.id)
        ]

    @pytest.mark.parametrize("endpoint", ["/api/leads/kanban/", "/api/leads/"])
    def test_invalid_email_status_is_rejected(self, admin_client, endpoint):
        response = admin_client.get(endpoint, {"email_status": "typo"})

        assert response.status_code == 400
        assert "email_status" in response.json()

    def test_email_status_filter_respects_tenant_boundary(
        self, admin_client, org_a, org_b, lead_email_factory
    ):
        lead_email_factory(
            org=org_b,
            name="Other tenant draft",
            draft_count=1,
        )
        _set_rls(org_a)

        response = admin_client.get(
            "/api/leads/kanban/", {"email_status": LeadEmailStatus.DRAFT}
        )

        assert response.status_code == 200
        assert _response_leads(response, "/api/leads/kanban/") == []

    def test_kanban_serializer_requires_email_annotations(
        self, org_a, lead_email_factory
    ):
        lead = lead_email_factory(org=org_a, name="Unannotated")

        with pytest.raises(AssertionError, match="with_email_activity"):
            LeadKanbanCardSerializer(lead).data

    @pg_only
    def test_kanban_custom_field_filter(self, admin_client, admin_user, org_a):
        """Kanban accepts the same cf_<key> filters as the lead list."""
        _set_rls(org_a)
        Lead.objects.create(
            company_name="Likely ZZP",
            email="likely-zzp@example.com",
            status="assigned",
            custom_fields={"partner_zzp_likelihood": "Hoog"},
            created_by=admin_user,
            org=org_a,
        )
        Lead.objects.create(
            company_name="Larger Company",
            email="larger-company@example.com",
            status="assigned",
            custom_fields={"partner_zzp_likelihood": "Laag"},
            created_by=admin_user,
            org=org_a,
        )

        response = admin_client.get(
            "/api/leads/kanban/", {"cf_partner_zzp_likelihood": "Hoog"}
        )

        assert response.status_code == 200
        assert response.json()["total_leads"] == 1

    def test_kanban_non_admin_sees_assigned_leads(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin user only sees assigned leads in kanban."""
        _set_rls(org_a)
        Lead.objects.create(
            first_name="Admin",
            last_name="Kanban",
            email="adminkb@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        assigned_lead = Lead.objects.create(
            first_name="Assigned",
            last_name="Kanban",
            email="assignedkb@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        assigned_lead.assigned_to.add(user_profile)
        response = user_client.get("/api/leads/kanban/")
        assert response.status_code == 200
        data = response.json()
        all_lead_emails = []
        for col in data["columns"]:
            for lead in col["leads"]:
                all_lead_emails.append(lead["email"])
        assert "assignedkb@example.com" in all_lead_emails
        assert "adminkb@example.com" not in all_lead_emails


@pytest.mark.django_db
class TestLeadMoveView:
    """Tests for PATCH /api/leads/<pk>/move/."""

    def test_move_lead_status(self, admin_client, admin_user, org_a):
        """Move a lead to a different status column."""
        _set_rls(org_a)
        lead = Lead.objects.create(
            first_name="Move",
            last_name="Lead",
            email="movelead@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.patch(
            f"/api/leads/{lead.id}/move/",
            {"status": "in process"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["error"] is False
        lead.refresh_from_db()
        assert lead.status == "in process"

    def test_move_lead_to_stage(self, admin_client, admin_user, org_a):
        """Move a lead to a pipeline stage."""
        _set_rls(org_a)
        pipeline = LeadPipeline.objects.create(
            name="Move Pipeline", org=org_a, created_by=admin_user
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline,
            name="Contacted",
            order=1,
            org=org_a,
            maps_to_status="in process",
        )
        lead = Lead.objects.create(
            first_name="Stage",
            last_name="Move",
            email="stagemove@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.patch(
            f"/api/leads/{lead.id}/move/",
            {"stage_id": str(stage.id)},
            format="json",
        )
        assert response.status_code == 200
        lead.refresh_from_db()
        assert lead.stage == stage
        assert lead.status == "in process"  # maps_to_status applied

    def test_move_lead_wip_limit_exceeded(self, admin_client, admin_user, org_a):
        """Moving a lead to a stage at WIP limit returns 400."""
        _set_rls(org_a)
        pipeline = LeadPipeline.objects.create(
            name="WIP Pipeline", org=org_a, created_by=admin_user
        )
        stage = LeadStage.objects.create(
            pipeline=pipeline,
            name="Limited",
            order=1,
            org=org_a,
            wip_limit=1,
        )
        Lead.objects.create(
            first_name="Existing",
            last_name="Lead",
            email="existing@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
            stage=stage,
        )
        lead2 = Lead.objects.create(
            first_name="Overflow",
            last_name="Lead",
            email="overflow@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.patch(
            f"/api/leads/{lead2.id}/move/",
            {"stage_id": str(stage.id)},
            format="json",
        )
        assert response.status_code == 400

    def test_move_lead_invalid_data(self, admin_client, admin_user, org_a):
        """Move with neither stage_id nor status returns 400."""
        _set_rls(org_a)
        lead = Lead.objects.create(
            first_name="Invalid",
            last_name="Move",
            email="invalidmove@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.patch(
            f"/api/leads/{lead.id}/move/",
            {},
            format="json",
        )
        assert response.status_code == 400

    def test_move_lead_non_admin_not_assigned_forbidden(
        self, user_client, admin_user, org_a, user_profile
    ):
        """Non-admin not assigned/creator cannot move a lead."""
        _set_rls(org_a)
        lead = Lead.objects.create(
            first_name="NoMove",
            last_name="Lead",
            email="nomove@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = user_client.patch(
            f"/api/leads/{lead.id}/move/",
            {"status": "closed"},
            format="json",
        )
        assert response.status_code == 403

    def test_move_lead_with_explicit_order(self, admin_client, admin_user, org_a):
        """Move lead with explicit kanban_order."""
        _set_rls(org_a)
        lead = Lead.objects.create(
            first_name="Order",
            last_name="Lead",
            email="orderlead@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.patch(
            f"/api/leads/{lead.id}/move/",
            {"status": "in process", "kanban_order": "5000.000000"},
            format="json",
        )
        assert response.status_code == 200
        lead.refresh_from_db()
        assert lead.kanban_order == 5000

    def test_move_lead_between_two_leads(self, admin_client, admin_user, org_a):
        """Move lead between two existing leads using above/below hints."""
        _set_rls(org_a)
        lead_above = Lead.objects.create(
            first_name="Above",
            last_name="Lead",
            email="above@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
            kanban_order=1000,
        )
        lead_below = Lead.objects.create(
            first_name="Below",
            last_name="Lead",
            email="below@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
            kanban_order=2000,
        )
        lead_to_move = Lead.objects.create(
            first_name="Moving",
            last_name="Lead",
            email="moving@example.com",
            status="assigned",
            created_by=admin_user,
            org=org_a,
        )
        response = admin_client.patch(
            f"/api/leads/{lead_to_move.id}/move/",
            {
                "status": "assigned",
                "above_lead_id": str(lead_above.id),
                "below_lead_id": str(lead_below.id),
            },
            format="json",
        )
        assert response.status_code == 200
        lead_to_move.refresh_from_db()
        assert lead_to_move.kanban_order == 1500  # midpoint
