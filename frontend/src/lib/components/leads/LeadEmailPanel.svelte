<script>
  import { Mail, Loader2, Reply, Send, ChevronDown, ChevronRight } from '@lucide/svelte';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Textarea } from '$lib/components/ui/textarea/index.js';
  import { Label } from '$lib/components/ui/label/index.js';

  /** @type {{ lead: any, mailboxes?: any[] }} */
  let { lead, mailboxes = [] } = $props();

  let threads = $state([]);
  let loading = $state(false);
  let sending = $state(false);
  let composeOpen = $state(false);
  let expandedThreadId = $state('');
  let mailboxId = $state('');
  let subject = $state('');
  let bodyText = $state('');
  let followUpDays = $state(5);
  let replyText = $state('');
  let loadedLeadId = $state('');

  const activeMailboxes = $derived(mailboxes.filter((mailbox) => mailbox.is_active));

  function leadName() {
    return [lead?.firstName, lead?.lastName].filter(Boolean).join(' ') || 'daar';
  }

  function resetComposer() {
    mailboxId = activeMailboxes[0]?.id || '';
    subject = 'Kennismaken als installatiepartner in regio Apeldoorn';
    bodyText = `Beste ${leadName()},

Wij zijn Bruens Duurzame Technieken uit Apeldoorn. Wij bezoeken de klant, maken de offerte, bestellen de materialen en bereiden het werk voor. Voor de uitvoering zoeken we betrouwbare installatiepartners.

Zou je openstaan voor een korte kennismaking om te bespreken welk type installatiewerk en welke regio bij je passen?

Met vriendelijke groet,
Bruens Duurzame Technieken`;
    followUpDays = 5;
  }

  async function loadThreads() {
    if (!lead?.id) return;
    loading = true;
    try {
      const response = await fetch(`/frontend-api/communications/leads/${lead.id}/threads`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'E-mails laden mislukt');
      threads = data.threads || [];
      if (threads.length && !expandedThreadId) expandedThreadId = threads[0].id;
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
      expandedThreadId = '';
      composeOpen = false;
      resetComposer();
      loadThreads();
    }
  });

  $effect(() => {
    if (!mailboxId && activeMailboxes.length) mailboxId = activeMailboxes[0].id;
  });

  async function sendEmail() {
    if (!mailboxId || !subject.trim() || !bodyText.trim()) return;
    sending = true;
    try {
      const response = await fetch(`/frontend-api/communications/leads/${lead.id}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mailbox_id: mailboxId,
          subject: subject.trim(),
          body_text: bodyText.trim(),
          follow_up_days: Number(followUpDays)
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'E-mail verzenden mislukt');
      toast.success(`E-mail verzonden naar ${lead.email}`);
      composeOpen = false;
      await loadThreads();
    } catch (err) {
      toast.error(err?.message || 'E-mail verzenden mislukt');
    } finally {
      sending = false;
    }
  }

  async function sendReply(threadId) {
    if (!replyText.trim()) return;
    sending = true;
    try {
      const response = await fetch(`/frontend-api/communications/threads/${threadId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body_text: replyText.trim() })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Antwoord verzenden mislukt');
      replyText = '';
      toast.success('Antwoord verzonden');
      await loadThreads();
    } catch (err) {
      toast.error(err?.message || 'Antwoord verzenden mislukt');
    } finally {
      sending = false;
    }
  }

  function formatDate(value) {
    return value ? new Date(value).toLocaleString('nl-NL') : '';
  }
</script>

<section class="space-y-3 border-b border-[var(--border-default)] pb-5">
  <div class="flex items-center justify-between gap-3">
    <div class="flex items-center gap-2">
      <Mail class="h-4 w-4 text-[var(--text-secondary)]" />
      <h3 class="text-sm font-semibold text-[var(--text-primary)]">E-mail</h3>
      {#if threads.length}
        <span class="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs">
          {threads.length}
        </span>
      {/if}
    </div>
    <Button
      type="button"
      size="sm"
      variant="outline"
      onclick={() => (composeOpen = !composeOpen)}
      disabled={!lead?.email || activeMailboxes.length === 0}
      class="gap-1.5"
    >
      <Send class="h-3.5 w-3.5" />
      Nieuwe e-mail
    </Button>
  </div>

  {#if !lead?.email}
    <p class="text-xs text-amber-700 dark:text-amber-300">
      Voeg eerst een e-mailadres toe aan deze lead.
    </p>
  {:else if activeMailboxes.length === 0}
    <p class="text-xs text-amber-700 dark:text-amber-300">
      Er is nog geen actieve Gmail-mailbox gekoppeld.
      <a href="/settings/email" class="underline">Open de e-mailinstellingen</a>.
    </p>
  {/if}

  {#if composeOpen}
    <div class="space-y-3 rounded-lg border border-[var(--border-default)] p-3">
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
        <Input id="lead-email-subject" bind:value={subject} maxlength="512" />
      </div>
      <div class="space-y-1">
        <Label for="lead-email-body">Bericht</Label>
        <Textarea id="lead-email-body" bind:value={bodyText} rows="10" />
      </div>
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
        <Button
          type="button"
          onclick={sendEmail}
          disabled={sending || !subject.trim() || !bodyText.trim()}
          class="gap-1.5"
        >
          {#if sending}<Loader2 class="h-3.5 w-3.5 animate-spin" />{/if}
          Verzenden
        </Button>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="flex items-center gap-2 py-2 text-xs text-[var(--text-secondary)]">
      <Loader2 class="h-3.5 w-3.5 animate-spin" />
      E-mails laden…
    </div>
  {:else if threads.length === 0}
    <p class="py-1 text-xs text-[var(--text-secondary)]">
      Nog geen e-mailgesprekken met deze lead.
    </p>
  {:else}
    <div class="space-y-2">
      {#each threads as thread (thread.id)}
        <article class="rounded-lg border border-[var(--border-default)]">
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 p-3 text-left"
            onclick={() => (expandedThreadId = expandedThreadId === thread.id ? '' : thread.id)}
          >
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium text-[var(--text-primary)]">
                {thread.subject}
              </span>
              <span class="block text-xs text-[var(--text-secondary)]">
                {formatDate(thread.last_message_at)}
                {#if thread.reply_received_at}
                  · antwoord ontvangen{/if}
              </span>
            </span>
            {#if expandedThreadId === thread.id}
              <ChevronDown class="h-4 w-4 shrink-0" />
            {:else}
              <ChevronRight class="h-4 w-4 shrink-0" />
            {/if}
          </button>

          {#if expandedThreadId === thread.id}
            <div class="space-y-3 border-t border-[var(--border-default)] p-3">
              {#each thread.messages as message (message.id)}
                <div
                  class:ml-5={message.direction === 'outbound'}
                  class:mr-5={message.direction === 'inbound'}
                  class="rounded-md bg-[var(--surface-muted)] p-3"
                >
                  <div
                    class="mb-2 flex justify-between gap-2 text-[11px] text-[var(--text-secondary)]"
                  >
                    <span>{message.direction === 'outbound' ? 'Verzonden' : 'Ontvangen'}</span>
                    <span>{formatDate(message.occurred_at)}</span>
                  </div>
                  <p class="whitespace-pre-wrap text-sm text-[var(--text-primary)]">
                    {message.body_text || '(Geen platte tekst beschikbaar)'}
                  </p>
                </div>
              {/each}
              <div class="space-y-2">
                <Textarea bind:value={replyText} rows="4" placeholder="Schrijf een antwoord…" />
                <div class="flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    onclick={() => sendReply(thread.id)}
                    disabled={sending || !replyText.trim()}
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
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>
