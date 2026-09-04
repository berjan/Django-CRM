<script>
  import {
    CheckCheck,
    FileEdit,
    Loader2,
    Mail,
    MessageCircle,
    RefreshCw,
    Reply,
    Send,
    Trash2,
    X
  } from '@lucide/svelte';
  import { resolve } from '$app/paths';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Textarea } from '$lib/components/ui/textarea/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import EmailSignaturePreview from '$lib/components/email/EmailSignaturePreview.svelte';

  /** @type {{ lead: any, mailboxes?: any[], templates?: any[], signature?: any, variant?: 'compact' | 'full', onunreadchange?: (count: number) => void, ondraftchange?: (count: number) => void }} */
  let {
    lead,
    mailboxes = [],
    templates = [],
    signature = null,
    variant = 'compact',
    onunreadchange = () => {},
    ondraftchange = () => {}
  } = $props();

  let threads = $state([]);
  let drafts = $state([]);
  let assignments = $state([]);
  let loading = $state(false);
  let syncing = $state(false);
  let sending = $state(false);
  let savingDraft = $state(false);
  let deletingDraftId = $state('');
  let composeOpen = $state(false);
  let selectedThreadId = $state('');
  let loadedLeadId = $state('');

  let mailboxId = $state('');
  let selectedTemplateId = $state('');
  let subject = $state('');
  let bodyText = $state('');
  let followUpDays = $state(5);
  let draftId = $state('');
  let assignAsDefault = $state(false);
  let savedSubject = $state('');
  let savedBodyText = $state('');
  let savedFollowUpDays = $state(5);

  let replyText = $state('');
  let replyTemplateId = $state('');
  let replyDraftId = $state('');
  let replyFollowUpDays = $state(5);

  const activeMailboxes = $derived(mailboxes.filter((mailbox) => mailbox.is_active));
  const activeTemplates = $derived(templates.filter((template) => template.is_active));
  const selectedThread = $derived(threads.find((thread) => thread.id === selectedThreadId) || null);
  const unreadTotal = $derived(
    threads.reduce((total, thread) => total + Number(thread.unread_count || 0), 0)
  );
  const openNewDrafts = $derived(
    drafts.filter((draft) => draft.status === 'draft' && !draft.thread)
  );
  const currentDraft = $derived(openNewDrafts.find((draft) => draft.id === draftId) || null);
  const hasUnsavedChanges = $derived(
    composeOpen &&
      (draftId
        ? subject !== savedSubject ||
          bodyText !== savedBodyText ||
          Number(followUpDays) !== Number(savedFollowUpDays)
        : Boolean(subject.trim() || bodyText.trim()))
  );

  $effect(() => {
    onunreadchange(unreadTotal);
  });

  $effect(() => {
    ondraftchange(openNewDrafts.length);
  });

  function resetNewComposer() {
    mailboxId = activeMailboxes[0]?.id || '';
    const defaultAssignment = assignments.find((assignment) => assignment.is_default);
    selectedTemplateId = defaultAssignment?.template?.id || activeTemplates[0]?.id || '';
    subject = '';
    bodyText = '';
    followUpDays = 5;
    draftId = '';
    assignAsDefault = Boolean(defaultAssignment);
    savedSubject = '';
    savedBodyText = '';
    savedFollowUpDays = 5;
  }

  function rememberSavedDraft(draft) {
    savedSubject = draft.subject || '';
    savedBodyText = draft.body_text || '';
    savedFollowUpDays = Number(draft.follow_up_days || 5);
  }

  function confirmDiscardChanges() {
    return (
      !hasUnsavedChanges ||
      window.confirm('Je hebt niet-opgeslagen wijzigingen. Wil je deze wijzigingen verwijderen?')
    );
  }

  function startNewEmail() {
    if (!confirmDiscardChanges()) return;
    resetNewComposer();
    composeOpen = true;
  }

  function closeComposer() {
    if (!confirmDiscardChanges()) return;
    composeOpen = false;
    resetNewComposer();
  }

  function loadReplyDraft(threadId) {
    const existing = drafts.find((draft) => draft.status === 'draft' && draft.thread === threadId);
    replyDraftId = existing?.id || '';
    replyTemplateId = existing?.template_id || '';
    replyText = existing?.body_text || '';
    replyFollowUpDays = existing?.follow_up_days || 5;
  }

  async function loadEmailWorkspace({ preserveSelection = true } = {}) {
    if (!lead?.id) return;
    loading = true;
    try {
      const [threadResponse, draftResponse, assignmentResponse] = await Promise.all([
        fetch(`/frontend-api/communications/leads/${lead.id}/threads`),
        fetch(`/frontend-api/communications/leads/${lead.id}/drafts`),
        fetch(`/frontend-api/communications/leads/${lead.id}/template-assignments`)
      ]);
      const [threadData, draftData, assignmentData] = await Promise.all([
        threadResponse.json(),
        draftResponse.json(),
        assignmentResponse.json()
      ]);
      if (!threadResponse.ok) throw new Error(threadData.error || 'E-mails laden mislukt');
      if (!draftResponse.ok) throw new Error(draftData.error || 'Concepten laden mislukt');
      if (!assignmentResponse.ok) {
        throw new Error(assignmentData.error || 'Template-toewijzingen laden mislukt');
      }
      threads = threadData.threads || [];
      drafts = draftData.results || [];
      assignments = assignmentData.results || [];
      const selectionStillExists = threads.some((thread) => thread.id === selectedThreadId);
      if (!preserveSelection || !selectionStillExists) {
        selectedThreadId = threads.find((thread) => thread.is_unread)?.id || threads[0]?.id || '';
      }
      if (selectedThreadId) loadReplyDraft(selectedThreadId);
      if (!draftId) resetNewComposer();
      const newDrafts = drafts.filter((draft) => draft.status === 'draft' && !draft.thread);
      if (variant === 'full' && threads.length === 0 && newDrafts.length === 1 && !composeOpen) {
        openDraft(newDrafts[0], { force: true });
      }
    } catch (err) {
      toast.error(err?.message || 'E-mails laden mislukt');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (lead?.id && lead.id !== loadedLeadId) {
      loadedLeadId = lead.id;
      threads = [];
      drafts = [];
      assignments = [];
      selectedThreadId = '';
      composeOpen = false;
      resetNewComposer();
      loadEmailWorkspace({ preserveSelection: false });
    }
  });

  $effect(() => {
    if (!mailboxId && activeMailboxes.length) mailboxId = activeMailboxes[0].id;
  });

  async function openThread(threadId) {
    selectedThreadId = threadId;
    loadReplyDraft(threadId);
    const thread = threads.find((item) => item.id === threadId);
    if (thread?.is_unread) await markThreadRead(threadId);
  }

  async function markThreadRead(threadId) {
    try {
      const response = await fetch(`/frontend-api/communications/threads/${threadId}/read`, {
        method: 'POST'
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Markeren als gelezen mislukt');
      threads = threads.map((thread) => (thread.id === data.id ? data : thread));
    } catch (err) {
      toast.error(err?.message || 'Markeren als gelezen mislukt');
    }
  }

  async function syncMailbox() {
    const syncMailboxId = selectedThread?.mailbox || activeMailboxes[0]?.id;
    if (!syncMailboxId) return;
    syncing = true;
    try {
      const response = await fetch(`/frontend-api/communications/mailboxes/${syncMailboxId}/sync`, {
        method: 'POST'
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Synchroniseren mislukt');
      await loadEmailWorkspace();
      toast.success(
        data.ingested ? `${data.ingested} nieuw(e) bericht(en) opgehaald` : 'E-mail is bijgewerkt'
      );
    } catch (err) {
      toast.error(err?.message || 'Synchroniseren mislukt');
    } finally {
      syncing = false;
    }
  }

  function openDraft(draft, { force = false } = {}) {
    if (draft.id === draftId && composeOpen) return;
    if (!force && draft.id !== draftId && !confirmDiscardChanges()) return;
    draftId = draft.id;
    mailboxId = draft.mailbox;
    selectedTemplateId = draft.template_id || '';
    subject = draft.subject;
    bodyText = draft.body_text;
    followUpDays = draft.follow_up_days;
    rememberSavedDraft(draft);
    composeOpen = true;
  }

  async function deleteDraft(draft) {
    if (
      !window.confirm(`Concept “${draft.subject || '(Geen onderwerp)'}” definitief verwijderen?`)
    ) {
      return;
    }
    deletingDraftId = draft.id;
    try {
      const response = await fetch(`/frontend-api/communications/drafts/${draft.id}`, {
        method: 'DELETE'
      });
      const data = response.status === 204 ? null : await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.error || 'Concept verwijderen mislukt');
      drafts = drafts.filter((item) => item.id !== draft.id);
      if (draft.id === draftId) {
        composeOpen = false;
        resetNewComposer();
      }
      toast.success('Concept verwijderd');
    } catch (err) {
      toast.error(err?.message || 'Concept verwijderen mislukt');
    } finally {
      deletingDraftId = '';
    }
  }

  async function saveTemplateAssignment() {
    if (!selectedTemplateId) return;
    const response = await fetch(
      `/frontend-api/communications/leads/${lead.id}/template-assignments`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedTemplateId,
          is_default: assignAsDefault
        })
      }
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Template-toewijzing opslaan mislukt');
    if (assignAsDefault) {
      assignments = assignments.map((assignment) => ({ ...assignment, is_default: false }));
    }
    const existing = assignments.findIndex((assignment) => assignment.id === data.id);
    assignments =
      existing >= 0
        ? assignments.map((assignment, index) => (index === existing ? data : assignment))
        : [...assignments, data];
  }

  async function createDraft() {
    if (!mailboxId) throw new Error('Kies eerst een mailbox');
    savingDraft = true;
    try {
      const payload = selectedTemplateId
        ? {
            mailbox_id: mailboxId,
            template_id: selectedTemplateId,
            follow_up_days: Number(followUpDays)
          }
        : {
            mailbox_id: mailboxId,
            subject: subject.trim(),
            body_text: bodyText.trim(),
            follow_up_days: Number(followUpDays)
          };
      const response = await fetch(`/frontend-api/communications/leads/${lead.id}/drafts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Concept maken mislukt');
      draftId = data.id;
      subject = data.subject;
      bodyText = data.body_text;
      followUpDays = data.follow_up_days;
      drafts = [data, ...drafts.filter((draft) => draft.id !== data.id)];
      rememberSavedDraft(data);
      if (selectedTemplateId) await saveTemplateAssignment();
      return data;
    } finally {
      savingDraft = false;
    }
  }

  async function saveDraft() {
    if (!draftId) return createDraft();
    savingDraft = true;
    try {
      const response = await fetch(`/frontend-api/communications/drafts/${draftId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subject: subject.trim(),
          body_text: bodyText.trim(),
          follow_up_days: Number(followUpDays)
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Concept opslaan mislukt');
      drafts = drafts.map((draft) => (draft.id === data.id ? data : draft));
      rememberSavedDraft(data);
      return data;
    } finally {
      savingDraft = false;
    }
  }

  async function prepareDraft() {
    try {
      await (draftId ? saveDraft() : createDraft());
      toast.success('Concept opgeslagen');
    } catch (err) {
      toast.error(err?.message || 'Concept opslaan mislukt');
    }
  }

  async function sendEmail() {
    if (!mailboxId) return;
    sending = true;
    try {
      if (!draftId) await createDraft();
      else await saveDraft();
      const response = await fetch(`/frontend-api/communications/drafts/${draftId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idempotency_key: crypto.randomUUID() })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'E-mail verzenden mislukt');
      toast.success(`E-mail verzonden naar ${lead.email}`);
      composeOpen = false;
      resetNewComposer();
      await loadEmailWorkspace({ preserveSelection: false });
    } catch (err) {
      toast.error(err?.message || 'E-mail verzenden mislukt');
    } finally {
      sending = false;
    }
  }

  async function ensureReplyDraft() {
    if (!selectedThreadId) throw new Error('Kies eerst een thread');
    savingDraft = true;
    try {
      if (replyDraftId) {
        const response = await fetch(`/frontend-api/communications/drafts/${replyDraftId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            body_text: replyText.trim(),
            follow_up_days: Number(replyFollowUpDays)
          })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Antwoordconcept opslaan mislukt');
        drafts = drafts.map((draft) => (draft.id === data.id ? data : draft));
        return data;
      }
      const payload = replyTemplateId
        ? {
            template_id: replyTemplateId,
            follow_up_days: Number(replyFollowUpDays)
          }
        : {
            body_text: replyText.trim(),
            follow_up_days: Number(replyFollowUpDays)
          };
      const response = await fetch(
        `/frontend-api/communications/threads/${selectedThreadId}/drafts`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Antwoordconcept maken mislukt');
      replyDraftId = data.id;
      replyText = data.body_text;
      drafts = [data, ...drafts.filter((draft) => draft.id !== data.id)];
      return data;
    } finally {
      savingDraft = false;
    }
  }

  async function saveReplyDraft() {
    try {
      await ensureReplyDraft();
      toast.success('Antwoordconcept opgeslagen');
      await loadEmailWorkspace();
    } catch (err) {
      toast.error(err?.message || 'Antwoordconcept opslaan mislukt');
    }
  }

  async function sendReply() {
    if (!selectedThreadId) return;
    sending = true;
    try {
      await ensureReplyDraft();
      const response = await fetch(`/frontend-api/communications/drafts/${replyDraftId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idempotency_key: crypto.randomUUID() })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Antwoord verzenden mislukt');
      toast.success('Antwoord verzonden');
      replyText = '';
      replyTemplateId = '';
      replyDraftId = '';
      await markThreadRead(selectedThreadId);
      await loadEmailWorkspace();
    } catch (err) {
      toast.error(err?.message || 'Antwoord verzenden mislukt');
    } finally {
      sending = false;
    }
  }

  function formatDate(value) {
    return value ? new Date(value).toLocaleString('nl-NL') : '';
  }

  function formatShortDate(value) {
    if (!value) return '';
    const date = new Date(value);
    const today = new Date();
    return date.toDateString() === today.toDateString()
      ? date.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })
      : date.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' });
  }

  function statusLabel(status) {
    return (
      {
        new_reply: 'Nieuw antwoord',
        reply_received: 'Antwoord ontvangen',
        waiting_for_reply: 'Wacht op antwoord',
        draft: 'Concept',
        empty: 'Leeg'
      }[status] || status
    );
  }

  function statusClass(status) {
    if (status === 'new_reply')
      return 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200';
    if (status === 'reply_received') {
      return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200';
    }
    if (status === 'draft') {
      return 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200';
    }
    return 'bg-[var(--surface-muted)] text-[var(--text-secondary)]';
  }
</script>

<section
  class={variant === 'full'
    ? 'space-y-4 py-4 pb-8'
    : 'space-y-3 border-b border-[var(--border-default)] pb-5'}
>
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex items-center gap-2">
      <Mail class="h-4 w-4 text-[var(--text-secondary)]" />
      <h3 class="text-sm font-semibold text-[var(--text-primary)]">E-mail</h3>
      {#if threads.length}
        <span class="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs">
          {threads.length} gesprek{threads.length === 1 ? '' : 'ken'}
        </span>
      {/if}
      {#if openNewDrafts.length}
        <span
          class="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200"
        >
          {openNewDrafts.length} concept{openNewDrafts.length === 1 ? '' : 'en'}
        </span>
      {/if}
      {#if unreadTotal}
        <span class="rounded-full bg-blue-600 px-2 py-0.5 text-xs text-white">
          {unreadTotal} nieuw
        </span>
      {/if}
    </div>
    <div class="flex gap-2">
      {#if variant === 'compact' && lead?.id}
        <Button type="button" size="sm" variant="ghost" href={`/leads/${lead.id}?tab=email`}>
          Volledige weergave
        </Button>
      {/if}
      <Button
        type="button"
        size="sm"
        variant="ghost"
        onclick={syncMailbox}
        disabled={syncing || activeMailboxes.length === 0}
        class="gap-1.5"
      >
        <RefreshCw class={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
        {variant === 'full' ? 'Vernieuwen' : ''}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onclick={startNewEmail}
        disabled={!lead?.email || activeMailboxes.length === 0}
        class="gap-1.5"
      >
        <Send class="h-3.5 w-3.5" />
        Nieuwe e-mail
      </Button>
    </div>
  </div>

  {#if !lead?.email}
    <p class="text-xs text-amber-700 dark:text-amber-300">
      Voeg eerst een e-mailadres toe aan deze lead.
    </p>
  {:else if activeMailboxes.length === 0}
    <p class="text-xs text-amber-700 dark:text-amber-300">
      Er is nog geen actieve Gmail-mailbox gekoppeld.
      <a href={resolve('/settings/email')} class="underline">Open de e-mailinstellingen</a>.
    </p>
  {/if}

  {#if openNewDrafts.length}
    <section
      class="overflow-hidden rounded-xl border border-amber-200 bg-amber-50/40 dark:border-amber-900 dark:bg-amber-950/10"
      aria-labelledby="lead-email-drafts-heading"
    >
      <div
        class="flex flex-wrap items-center justify-between gap-2 border-b border-amber-200 px-4 py-3 dark:border-amber-900"
      >
        <div class="flex items-center gap-2">
          <FileEdit class="h-4 w-4 text-amber-700 dark:text-amber-300" />
          <h4
            id="lead-email-drafts-heading"
            class="text-sm font-semibold text-[var(--text-primary)]"
          >
            Concepten
          </h4>
          <span class="text-xs text-[var(--text-secondary)]"> Nog niet verzonden </span>
        </div>
      </div>
      <div class="divide-y divide-amber-200 dark:divide-amber-900">
        {#each openNewDrafts as draft (draft.id)}
          <div
            class={[
              'flex flex-wrap items-center gap-3 px-4 py-3 transition-colors',
              draft.id === draftId
                ? 'bg-amber-100/70 dark:bg-amber-950/30'
                : 'hover:bg-amber-100/40 dark:hover:bg-amber-950/20'
            ]}
          >
            <button
              type="button"
              class="min-w-[220px] flex-1 text-left"
              onclick={() => openDraft(draft)}
              aria-current={draft.id === draftId ? 'true' : undefined}
            >
              <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="truncate text-sm font-medium text-[var(--text-primary)]">
                  {draft.subject || '(Geen onderwerp)'}
                </span>
                <span
                  class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                >
                  Concept
                </span>
              </span>
              <span class="mt-1 block text-xs text-[var(--text-secondary)]">
                Aan {draft.recipient}
                <span aria-hidden="true"> · </span>
                Gewijzigd {formatDate(draft.updated_at)}
              </span>
            </button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onclick={() => openDraft(draft)}
              disabled={deletingDraftId === draft.id}
            >
              Verder schrijven
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onclick={() => deleteDraft(draft)}
              disabled={deletingDraftId === draft.id}
              aria-label="Concept verwijderen"
              class="text-[var(--text-secondary)] hover:text-red-700"
            >
              {#if deletingDraftId === draft.id}
                <Loader2 class="h-4 w-4 animate-spin" />
              {:else}
                <Trash2 class="h-4 w-4" />
              {/if}
            </Button>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if composeOpen}
    <div
      class="space-y-3 rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)] p-4"
    >
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 class="text-sm font-semibold text-[var(--text-primary)]">
            {draftId ? 'Concept bewerken' : 'Nieuwe e-mail'}
          </h4>
          <p class="mt-1 text-xs text-[var(--text-secondary)]">
            {#if draftId && hasUnsavedChanges}
              Niet-opgeslagen wijzigingen
            {:else if currentDraft}
              Opgeslagen {formatDate(currentDraft.updated_at)}
            {:else}
              De e-mail wordt pas verstuurd wanneer je op Verzenden klikt.
            {/if}
          </p>
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onclick={closeComposer}
          aria-label="E-maileditor sluiten"
        >
          <X class="h-4 w-4" />
        </Button>
      </div>
      <div class="space-y-1">
        <Label for="lead-email-template">Template</Label>
        <select
          id="lead-email-template"
          bind:value={selectedTemplateId}
          onchange={() => {
            draftId = '';
            subject = '';
            bodyText = '';
            assignAsDefault = Boolean(
              assignments.find(
                (assignment) =>
                  assignment.template?.id === selectedTemplateId && assignment.is_default
              )
            );
          }}
          class="h-9 w-full rounded-md border border-[var(--border-default)] bg-[var(--surface-default)] px-3 text-sm"
        >
          <option value="">Zonder template</option>
          {#each activeTemplates as template (template.id)}
            <option value={template.id}>
              {template.name} (v{template.current_version})
            </option>
          {/each}
        </select>
        {#if selectedTemplateId}
          <label class="flex items-center gap-2 pt-1 text-xs text-[var(--text-secondary)]">
            <input type="checkbox" bind:checked={assignAsDefault} />
            Aan deze lead toekennen{assignAsDefault ? ' en als standaard gebruiken' : ''}
          </label>
        {/if}
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div class="space-y-1">
          <Label for="lead-email-from">Van</Label>
          <select
            id="lead-email-from"
            bind:value={mailboxId}
            class="h-9 w-full rounded-md border border-[var(--border-default)] bg-[var(--surface-default)] px-3 text-sm"
          >
            {#each activeMailboxes as mailbox (mailbox.id)}
              <option value={mailbox.id}>{mailbox.email_address}</option>
            {/each}
          </select>
        </div>
        <div class="space-y-1">
          <Label for="lead-email-to">Aan</Label>
          <Input id="lead-email-to" value={lead.email} disabled />
        </div>
      </div>
      <div class="space-y-1">
        <Label for="lead-email-subject">Onderwerp</Label>
        <Input
          id="lead-email-subject"
          bind:value={subject}
          maxlength="512"
          placeholder={selectedTemplateId ? 'Pas eerst de template toe' : 'Onderwerp'}
        />
      </div>
      <div class="space-y-1">
        <Label for="lead-email-body">Bericht</Label>
        <Textarea id="lead-email-body" bind:value={bodyText} rows="8" />
      </div>
      {#if signature?.is_enabled}
        <details class="rounded-md border border-[var(--border-default)] bg-white p-3">
          <summary class="cursor-pointer text-xs font-medium text-[var(--text-secondary)]">
            Vaste Bruens-handtekening · wordt automatisch toegevoegd
          </summary>
          <div class="mt-3 border-t border-[var(--border-default)] pt-3">
            <EmailSignaturePreview {signature} compact={variant !== 'full'} />
          </div>
        </details>
      {/if}
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="w-40 space-y-1">
          <Label for="lead-email-follow-up">Opvolgen na dagen</Label>
          <Input
            id="lead-email-follow-up"
            type="number"
            min="1"
            max="30"
            bind:value={followUpDays}
          />
        </div>
        <div class="flex gap-2">
          <Button
            type="button"
            variant="outline"
            onclick={prepareDraft}
            disabled={savingDraft || (!selectedTemplateId && (!subject.trim() || !bodyText.trim()))}
          >
            {#if savingDraft}<Loader2 class="mr-1.5 h-3.5 w-3.5 animate-spin" />{/if}
            {selectedTemplateId && !draftId ? 'Template toepassen' : 'Concept opslaan'}
          </Button>
          <Button
            type="button"
            onclick={sendEmail}
            disabled={sending || (!selectedTemplateId && (!subject.trim() || !bodyText.trim()))}
            class="gap-1.5"
          >
            {#if sending}<Loader2 class="h-3.5 w-3.5 animate-spin" />{/if}
            Verzenden
          </Button>
        </div>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="flex items-center gap-2 py-6 text-sm text-[var(--text-secondary)]">
      <Loader2 class="h-4 w-4 animate-spin" />
      E-mail laden…
    </div>
  {:else if threads.length === 0 && openNewDrafts.length === 0 && !composeOpen}
    <div
      class="rounded-lg border border-dashed border-[var(--border-default)] p-8 text-center text-sm text-[var(--text-secondary)]"
    >
      <MessageCircle class="mx-auto mb-2 h-8 w-8 text-[var(--text-tertiary)]" />
      <p class="font-medium text-[var(--text-primary)]">Nog geen e-mail met deze lead</p>
      <p class="mt-1">Maak een eerste e-mail of sla een concept op om hier te beginnen.</p>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onclick={startNewEmail}
        disabled={!lead?.email || activeMailboxes.length === 0}
        class="mt-4 gap-1.5"
      >
        <Send class="h-3.5 w-3.5" />
        Nieuwe e-mail
      </Button>
    </div>
  {:else if threads.length}
    <div
      class={variant === 'full'
        ? 'grid min-h-[580px] overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--surface-default)] lg:grid-cols-[300px_minmax(0,1fr)]'
        : 'space-y-3'}
    >
      <aside
        class={variant === 'full'
          ? 'border-b border-[var(--border-default)] bg-[var(--surface-muted)]/40 lg:border-r lg:border-b-0'
          : 'space-y-2'}
      >
        {#if variant === 'full'}
          <div
            class="border-b border-[var(--border-default)] px-4 py-3 text-xs font-semibold text-[var(--text-secondary)]"
          >
            Threads
          </div>
        {/if}
        <div class={variant === 'full' ? 'divide-y divide-[var(--border-default)]' : 'space-y-2'}>
          {#each threads as thread (thread.id)}
            <button
              type="button"
              class={[
                'relative w-full p-3 text-left transition-colors',
                variant === 'full' ? 'hover:bg-[var(--surface-default)]' : 'rounded-lg border',
                selectedThreadId === thread.id
                  ? 'border-[var(--color-primary-default)] bg-[var(--surface-default)]'
                  : 'border-[var(--border-default)]',
                thread.is_unread ? 'font-medium' : ''
              ]}
              onclick={() => openThread(thread.id)}
            >
              <span class="flex items-start justify-between gap-2">
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-2">
                    {#if thread.is_unread}
                      <span class="h-2 w-2 shrink-0 rounded-full bg-blue-600"></span>
                    {/if}
                    <span class="block truncate text-sm text-[var(--text-primary)]">
                      {thread.subject || '(Geen onderwerp)'}
                    </span>
                  </span>
                  <span class="mt-1 block truncate text-xs text-[var(--text-secondary)]">
                    {thread.latest_snippet || 'Nog geen berichttekst'}
                  </span>
                  <span class="mt-2 flex flex-wrap items-center gap-1.5">
                    <span
                      class={`rounded-full px-2 py-0.5 text-[10px] ${statusClass(thread.status)}`}
                    >
                      {statusLabel(thread.status)}
                    </span>
                    <span class="text-[10px] text-[var(--text-tertiary)]">
                      {thread.message_count} bericht{thread.message_count === 1 ? '' : 'en'}
                    </span>
                  </span>
                </span>
                <span class="shrink-0 text-[10px] text-[var(--text-tertiary)]">
                  {formatShortDate(thread.last_message_at)}
                </span>
              </span>
            </button>
          {/each}
        </div>
      </aside>

      {#if selectedThread}
        <article class="flex min-w-0 flex-col">
          <header
            class="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border-default)] px-4 py-3"
          >
            <div class="min-w-0">
              <h4 class="truncate text-sm font-semibold text-[var(--text-primary)]">
                {selectedThread.subject || '(Geen onderwerp)'}
              </h4>
              <p class="mt-1 text-xs text-[var(--text-secondary)]">
                {selectedThread.mailbox_email} ↔ {lead.email}
              </p>
            </div>
            <div class="flex items-center gap-2">
              {#if selectedThread.is_unread}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onclick={() => markThreadRead(selectedThread.id)}
                  class="gap-1.5"
                >
                  <CheckCheck class="h-3.5 w-3.5" />
                  Markeer gelezen
                </Button>
              {/if}
              <span class={`rounded-full px-2 py-1 text-xs ${statusClass(selectedThread.status)}`}>
                {statusLabel(selectedThread.status)}
              </span>
            </div>
          </header>

          <div class="flex-1 space-y-4 overflow-y-auto bg-[var(--surface-muted)]/20 p-4">
            {#each selectedThread.messages as message (message.id)}
              {@const visibleBody = message.body_preview || message.body_text || ''}
              <div
                class={`flex ${message.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  class={[
                    'max-w-[88%] rounded-xl border p-4 shadow-sm',
                    message.direction === 'outbound'
                      ? 'border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40'
                      : 'border-[var(--border-default)] bg-[var(--surface-default)]'
                  ]}
                >
                  <div
                    class="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[11px] text-[var(--text-secondary)]"
                  >
                    <span class="font-medium text-[var(--text-primary)]">
                      {message.direction === 'outbound'
                        ? selectedThread.mailbox_email
                        : message.from_address}
                    </span>
                    <span>{formatDate(message.occurred_at)}</span>
                  </div>
                  <p class="whitespace-pre-wrap text-sm leading-6 text-[var(--text-primary)]">
                    {visibleBody || '(Geen platte tekst beschikbaar)'}
                  </p>
                  {#if (message.body_text || '').trim().length > visibleBody.length}
                    <details class="mt-3 border-t border-[var(--border-default)] pt-2">
                      <summary class="cursor-pointer text-xs text-[var(--text-secondary)]">
                        Volledig bericht bekijken
                      </summary>
                      <p
                        class="mt-2 whitespace-pre-wrap text-xs leading-5 text-[var(--text-secondary)]"
                      >
                        {message.body_text}
                      </p>
                    </details>
                  {/if}
                </div>
              </div>
            {/each}
          </div>

          <div class="space-y-3 border-t border-[var(--border-default)] p-4">
            <div class="flex flex-wrap items-end gap-3">
              <div class="min-w-[220px] flex-1 space-y-1">
                <Label for="reply-template-{selectedThread.id}">Antwoordtemplate</Label>
                <select
                  id="reply-template-{selectedThread.id}"
                  bind:value={replyTemplateId}
                  onchange={() => {
                    replyDraftId = '';
                    replyText = '';
                  }}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-[var(--surface-default)] px-3 text-sm"
                >
                  <option value="">Zonder template</option>
                  {#each activeTemplates as template (template.id)}
                    <option value={template.id}>{template.name}</option>
                  {/each}
                </select>
              </div>
              <div class="w-36 space-y-1">
                <Label for="reply-follow-up-{selectedThread.id}">Opvolgen na</Label>
                <Input
                  id="reply-follow-up-{selectedThread.id}"
                  type="number"
                  min="1"
                  max="30"
                  bind:value={replyFollowUpDays}
                />
              </div>
            </div>
            <Textarea
              bind:value={replyText}
              rows={variant === 'full' ? 6 : 4}
              placeholder={replyTemplateId
                ? 'Pas de template toe om het antwoord te bekijken…'
                : 'Schrijf een antwoord…'}
            />
            {#if signature?.is_enabled}
              <p class="text-xs text-[var(--text-tertiary)]">
                De vaste Bruens-handtekening wordt automatisch onder dit antwoord geplaatst.
              </p>
            {/if}
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="text-xs text-[var(--text-tertiary)]">
                {replyDraftId ? 'Concept opgeslagen' : 'Wordt in dezelfde Gmail-thread verzonden'}
              </span>
              <div class="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onclick={saveReplyDraft}
                  disabled={savingDraft || (!replyTemplateId && !replyText.trim())}
                  class="gap-1.5"
                >
                  {#if savingDraft}
                    <Loader2 class="h-3.5 w-3.5 animate-spin" />
                  {:else}
                    <FileEdit class="h-3.5 w-3.5" />
                  {/if}
                  {replyTemplateId && !replyDraftId ? 'Template toepassen' : 'Concept opslaan'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onclick={sendReply}
                  disabled={sending || (!replyTemplateId && !replyText.trim())}
                  class="gap-1.5"
                >
                  {#if sending}
                    <Loader2 class="h-3.5 w-3.5 animate-spin" />
                  {:else}
                    <Reply class="h-3.5 w-3.5" />
                  {/if}
                  Antwoorden
                </Button>
              </div>
            </div>
          </div>
        </article>
      {:else}
        <div class="flex min-h-64 items-center justify-center text-sm text-[var(--text-secondary)]">
          Kies een thread om het gesprek te bekijken.
        </div>
      {/if}
    </div>
  {/if}
</section>
