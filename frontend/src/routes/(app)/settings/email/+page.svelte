<script>
  import { enhance } from '$app/forms';
  import { invalidateAll } from '$app/navigation';
  import {
    Mail,
    RefreshCw,
    Unplug,
    AlertTriangle,
    CheckCircle2,
    Plus,
    Copy,
    Save,
    Archive
  } from '@lucide/svelte';
  import { toast } from 'svelte-sonner';
  import { PageHeader } from '$lib/components/layout';
  import { Button } from '$lib/components/ui/button/index.js';
  import EmailSignaturePreview from '$lib/components/email/EmailSignaturePreview.svelte';

  /** @type {{ data: any, form: any }} */
  let { data, form } = $props();

  $effect(() => {
    if (data.connected) toast.success('Gmail is gekoppeld');
    if (data.oauthError) toast.error(`Gmail koppelen mislukt: ${data.oauthError}`);
    if (form?.error) toast.error(form.error);
    if (form?.synced !== undefined) {
      toast.success(`${form.synced} nieuw(e) bericht(en) gesynchroniseerd`);
      invalidateAll();
    }
    if (form?.disconnected) {
      toast.success('Mailbox is losgekoppeld');
      invalidateAll();
    }
    if (form?.templateCreated) {
      toast.success('E-mailtemplate gemaakt');
      invalidateAll();
    }
    if (form?.templateUpdated) {
      toast.success('E-mailtemplate opgeslagen');
      invalidateAll();
    }
    if (form?.templateDuplicated) {
      toast.success('E-mailtemplate gedupliceerd');
      invalidateAll();
    }
    if (form?.templateDeactivated) {
      toast.success('E-mailtemplate gedeactiveerd');
      invalidateAll();
    }
    if (form?.signatureUpdated) {
      toast.success('E-mailhandtekening opgeslagen');
      invalidateAll();
    }
  });
</script>

<svelte:head>
  <title>Lead Email - Settings - BottleCRM</title>
</svelte:head>

<PageHeader
  title="Lead Email"
  subtitle="Koppel Gmail om vanuit leads te mailen en antwoorden automatisch vast te leggen"
/>

<div class="flex-1 p-4 md:p-6 lg:p-8">
  <div class="mx-auto max-w-4xl space-y-6">
    {#if !data.configured}
      <section
        class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
      >
        <div class="flex gap-2">
          <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p class="font-medium">Google OAuth is nog niet geconfigureerd.</p>
            <p class="mt-1">
              Stel de Gmail client-id, client-secret en redirect-URL in op de server voordat je een
              mailbox koppelt.
            </p>
          </div>
        </div>
      </section>
    {/if}

    <section
      class="rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)] p-5"
    >
      <div>
        <h2 class="font-semibold text-[var(--text-primary)]">Vaste e-mailhandtekening</h2>
        <p class="mt-1 text-sm text-[var(--text-secondary)]">
          Deze handtekening wordt automatisch onder iedere eerste e-mail en ieder antwoord gezet.
          Zet hem daarom niet in de losse berichttemplates.
        </p>
      </div>

      {#if data.emailSignature}
        <div
          class="mt-5 overflow-x-auto rounded-lg border border-[var(--border-default)] bg-white p-5"
        >
          <EmailSignaturePreview signature={data.emailSignature} />
        </div>
        <form method="POST" action="?/updateSignature" use:enhance class="mt-5 space-y-4">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="space-y-1 text-sm">
              <span>Naam afzender</span>
              <input
                name="sender_name"
                required
                value={data.emailSignature.sender_name}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              />
            </label>
            <label class="space-y-1 text-sm">
              <span>Functie</span>
              <input
                name="sender_role"
                value={data.emailSignature.sender_role}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              />
            </label>
            <label class="space-y-1 text-sm">
              <span>Bedrijfsnaam</span>
              <input
                name="company_name"
                required
                value={data.emailSignature.company_name}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              />
            </label>
            <label class="space-y-1 text-sm">
              <span>Telefoonnummer</span>
              <input
                name="phone_number"
                value={data.emailSignature.phone_number}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              />
            </label>
            <label class="space-y-1 text-sm">
              <span>E-mailadres</span>
              <input
                name="email_address"
                type="email"
                required
                value={data.emailSignature.email_address}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              />
            </label>
            <label class="space-y-1 text-sm">
              <span>Website</span>
              <input
                name="website_url"
                type="url"
                value={data.emailSignature.website_url}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              />
            </label>
          </div>
          <label class="block space-y-1 text-sm">
            <span>Adres</span>
            <input
              name="address"
              value={data.emailSignature.address}
              class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
            />
          </label>
          <label class="block space-y-1 text-sm">
            <span>Logo-URL</span>
            <input
              name="logo_url"
              type="url"
              value={data.emailSignature.logo_url}
              class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
            />
          </label>
          <div class="grid gap-3 md:grid-cols-2">
            <label class="space-y-1 text-sm">
              <span>Primaire kleur</span>
              <input
                name="primary_color"
                type="color"
                value={data.emailSignature.primary_color}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent p-1"
              />
            </label>
            <label class="space-y-1 text-sm">
              <span>Accentkleur</span>
              <input
                name="accent_color"
                type="color"
                value={data.emailSignature.accent_color}
                class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent p-1"
              />
            </label>
          </div>

          <fieldset class="space-y-3">
            <legend class="text-sm font-medium">Reviews en projecten</legend>
            <div class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm">
                <span>Reviewscore</span>
                <input
                  name="review_score"
                  type="number"
                  min="0"
                  max="10"
                  step="0.1"
                  value={data.emailSignature.review_score || ''}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                />
              </label>
              <label class="space-y-1 text-sm">
                <span>Aantal beoordelingen</span>
                <input
                  name="review_count"
                  type="number"
                  min="0"
                  value={data.emailSignature.review_count || ''}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                />
              </label>
            </div>
            <div class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm">
                <span>Link naar alle reviews</span>
                <input
                  name="reviews_url"
                  type="url"
                  value={data.emailSignature.reviews_url || ''}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                />
              </label>
              <label class="space-y-1 text-sm">
                <span>Link naar projecten</span>
                <input
                  name="projects_url"
                  type="url"
                  value={data.emailSignature.projects_url || ''}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                />
              </label>
            </div>
          </fieldset>

          <fieldset class="space-y-3">
            <legend class="text-sm font-medium">Certificeringen</legend>
            {#each [0, 1, 2] as index (index)}
              {@const certification = data.emailSignature.certifications?.[index] || {}}
              <div class="grid gap-2 rounded-md bg-[var(--surface-muted)] p-3 md:grid-cols-3">
                <label class="space-y-1 text-xs">
                  <span>Naam</span>
                  <input
                    name={`cert_${index + 1}_name`}
                    value={certification.name || ''}
                    class="h-9 w-full rounded-md border border-[var(--border-default)] bg-[var(--surface-default)] px-3"
                  />
                </label>
                <label class="space-y-1 text-xs">
                  <span>Bewijspagina</span>
                  <input
                    name={`cert_${index + 1}_url`}
                    type="url"
                    value={certification.url || ''}
                    class="h-9 w-full rounded-md border border-[var(--border-default)] bg-[var(--surface-default)] px-3"
                  />
                </label>
                <label class="space-y-1 text-xs">
                  <span>Logo-URL</span>
                  <input
                    name={`cert_${index + 1}_image_url`}
                    type="url"
                    value={certification.image_url || ''}
                    class="h-9 w-full rounded-md border border-[var(--border-default)] bg-[var(--surface-default)] px-3"
                  />
                </label>
              </div>
            {/each}
          </fieldset>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" name="is_enabled" checked={data.emailSignature.is_enabled} />
              Automatisch toevoegen
            </label>
            <Button type="submit" class="gap-1.5"
              ><Save class="h-4 w-4" /> Handtekening opslaan</Button
            >
          </div>
        </form>
      {:else}
        <p class="mt-4 text-sm text-amber-700">Er is nog geen handtekening geconfigureerd.</p>
      {/if}
    </section>

    <section
      class="rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)] p-5"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 class="font-semibold text-[var(--text-primary)]">Gmail-mailboxen</h2>
          <p class="mt-1 text-sm text-[var(--text-secondary)]">
            Alleen e-mailgesprekken die vanuit een CRM-lead gestart zijn, worden opgeslagen.
          </p>
        </div>
        <form method="POST" action="?/connect">
          <Button type="submit" disabled={!data.configured} class="gap-2">
            <Mail class="h-4 w-4" />
            Gmail koppelen
          </Button>
        </form>
      </div>
    </section>

    {#if data.mailboxes.length === 0}
      <section
        class="rounded-lg border border-dashed border-[var(--border-default)] p-8 text-center text-sm text-[var(--text-secondary)]"
      >
        <Mail class="mx-auto mb-3 h-9 w-9 text-[var(--text-tertiary)]" />
        <p>Nog geen Gmail-mailbox gekoppeld.</p>
      </section>
    {:else}
      <ul class="space-y-3">
        {#each data.mailboxes as mailbox (mailbox.id)}
          <li
            class="rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)] p-5"
          >
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div class="flex gap-3">
                <span
                  class="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-primary-light)]"
                >
                  <Mail class="h-4 w-4 text-[var(--color-primary-default)]" />
                </span>
                <div>
                  <div class="flex items-center gap-2">
                    <p class="font-medium text-[var(--text-primary)]">{mailbox.email_address}</p>
                    {#if mailbox.is_active}
                      <CheckCircle2 class="h-4 w-4 text-emerald-600" aria-label="Actief" />
                    {/if}
                  </div>
                  <p class="mt-1 text-xs text-[var(--text-secondary)]">
                    {#if mailbox.last_synced_at}
                      Laatst gesynchroniseerd:
                      {new Date(mailbox.last_synced_at).toLocaleString('nl-NL')}
                    {:else}
                      Nog niet gesynchroniseerd
                    {/if}
                  </p>
                  {#if mailbox.last_error}
                    <p class="mt-2 text-xs text-amber-700 dark:text-amber-300">
                      {mailbox.last_error}
                    </p>
                  {/if}
                </div>
              </div>

              <div class="flex gap-2">
                {#if mailbox.is_active}
                  <form method="POST" action="?/sync" use:enhance>
                    <input type="hidden" name="id" value={mailbox.id} />
                    <Button type="submit" variant="outline" size="sm" class="gap-1.5">
                      <RefreshCw class="h-3.5 w-3.5" />
                      Synchroniseren
                    </Button>
                  </form>
                  <form method="POST" action="?/disconnect" use:enhance>
                    <input type="hidden" name="id" value={mailbox.id} />
                    <Button type="submit" variant="outline" size="sm" class="gap-1.5">
                      <Unplug class="h-3.5 w-3.5" />
                      Loskoppelen
                    </Button>
                  </form>
                {:else}
                  <span class="text-sm text-[var(--text-secondary)]">Losgekoppeld</span>
                {/if}
              </div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}

    <section
      class="rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)] p-5"
    >
      <div>
        <h2 class="font-semibold text-[var(--text-primary)]">Nieuwe e-mailtemplate</h2>
        <p class="mt-1 text-sm text-[var(--text-secondary)]">
          Templates worden veilig op de server ingevuld. Elke inhoudswijziging krijgt automatisch
          een nieuwe versie.
        </p>
      </div>
      <form method="POST" action="?/createTemplate" use:enhance class="mt-4 space-y-3">
        <div class="grid gap-3 md:grid-cols-2">
          <label class="space-y-1 text-sm">
            <span>Naam</span>
            <input
              name="name"
              required
              class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              placeholder="Installatiepartner – eerste contact"
            />
          </label>
          <label class="space-y-1 text-sm">
            <span>Doel</span>
            <input
              name="purpose"
              class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
              placeholder="installer_outreach"
            />
          </label>
        </div>
        <label class="block space-y-1 text-sm">
          <span>Beschrijving</span>
          <input
            name="description"
            class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
          />
        </label>
        <label class="block space-y-1 text-sm">
          <span>Onderwerp</span>
          <input
            name="subject"
            required
            class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
          />
        </label>
        <label class="block space-y-1 text-sm">
          <span>Bericht (platte tekst)</span>
          <textarea
            name="body_text"
            required
            rows="8"
            class="w-full rounded-md border border-[var(--border-default)] bg-transparent px-3 py-2"
          ></textarea>
        </label>
        <div class="flex justify-end">
          <Button type="submit" class="gap-1.5"><Plus class="h-4 w-4" /> Template maken</Button>
        </div>
      </form>
    </section>

    <section class="space-y-3">
      <div>
        <h2 class="font-semibold text-[var(--text-primary)]">E-mailtemplates</h2>
        <p class="mt-1 text-sm text-[var(--text-secondary)]">
          {data.templates.length} template(s). Inactieve templates blijven bewaard voor de verzendhistorie.
        </p>
      </div>
      {#each data.templates as template (template.id)}
        <details
          class="rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)]"
        >
          <summary class="cursor-pointer list-none p-5">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-medium text-[var(--text-primary)]">{template.name}</span>
                  <span class="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-xs">
                    v{template.current_version}
                  </span>
                  {#if !template.is_active}
                    <span class="text-xs text-amber-700 dark:text-amber-300">Inactief</span>
                  {/if}
                </div>
                <p class="mt-1 text-sm text-[var(--text-secondary)]">{template.subject}</p>
              </div>
              <span class="text-xs text-[var(--text-secondary)]">
                {template.usage_count}× gebruikt
              </span>
            </div>
          </summary>
          <div class="border-t border-[var(--border-default)] p-5">
            <form method="POST" action="?/updateTemplate" use:enhance class="space-y-3">
              <input type="hidden" name="id" value={template.id} />
              <div class="grid gap-3 md:grid-cols-2">
                <label class="space-y-1 text-sm">
                  <span>Naam</span>
                  <input
                    name="name"
                    required
                    value={template.name}
                    class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                  />
                </label>
                <label class="space-y-1 text-sm">
                  <span>Doel</span>
                  <input
                    name="purpose"
                    value={template.purpose}
                    class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                  />
                </label>
              </div>
              <label class="block space-y-1 text-sm">
                <span>Beschrijving</span>
                <input
                  name="description"
                  value={template.description}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                />
              </label>
              <label class="block space-y-1 text-sm">
                <span>Onderwerp</span>
                <input
                  name="subject"
                  required
                  value={template.subject}
                  class="h-9 w-full rounded-md border border-[var(--border-default)] bg-transparent px-3"
                />
              </label>
              <label class="block space-y-1 text-sm">
                <span>Bericht</span>
                <textarea
                  name="body_text"
                  required
                  rows="8"
                  class="w-full rounded-md border border-[var(--border-default)] bg-transparent px-3 py-2"
                  >{template.body_text}</textarea
                >
              </label>
              <label class="flex items-center gap-2 text-sm">
                <input type="checkbox" name="is_active" checked={template.is_active} />
                Actief
              </label>
              <div class="flex flex-wrap justify-end gap-2">
                <Button type="submit" variant="outline" class="gap-1.5">
                  <Save class="h-3.5 w-3.5" /> Opslaan
                </Button>
              </div>
            </form>
            <div class="mt-3 flex flex-wrap justify-end gap-2">
              <form method="POST" action="?/duplicateTemplate" use:enhance>
                <input type="hidden" name="id" value={template.id} />
                <input type="hidden" name="name" value="Kopie van {template.name}" />
                <Button type="submit" variant="outline" size="sm" class="gap-1.5">
                  <Copy class="h-3.5 w-3.5" /> Dupliceren
                </Button>
              </form>
              {#if template.is_active}
                <form method="POST" action="?/deactivateTemplate" use:enhance>
                  <input type="hidden" name="id" value={template.id} />
                  <Button type="submit" variant="outline" size="sm" class="gap-1.5">
                    <Archive class="h-3.5 w-3.5" /> Deactiveren
                  </Button>
                </form>
              {/if}
            </div>
          </div>
        </details>
      {/each}
    </section>

    <section
      class="rounded-lg border border-[var(--border-default)] bg-[var(--surface-default)] p-5"
    >
      <h2 class="font-semibold text-[var(--text-primary)]">Beschikbare variabelen</h2>
      <p class="mt-1 text-sm text-[var(--text-secondary)]">
        Gebruik exact deze notatie. Verzenden wordt geblokkeerd wanneer een gebruikte waarde
        ontbreekt.
      </p>
      <div class="mt-3 grid gap-2 md:grid-cols-2">
        {#each data.templateVariables as variable (variable.name)}
          <div class="rounded-md bg-[var(--surface-muted)] p-2 text-xs">
            <code>{`{{ ${variable.name} }}`}</code>
            <span class="mt-1 block text-[var(--text-secondary)]">{variable.description}</span>
          </div>
        {/each}
      </div>
    </section>
  </div>
</div>
