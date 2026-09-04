<script>
  import { AlertCircle, Mail, MessageSquare, Send } from '@lucide/svelte';
  import { getLeadEmailStatusPresentation } from '$lib/constants/lead-email-status.js';

  /** @type {{ status: string, draftCount?: number, lastEmailAt?: string|null }} */
  let { status, draftCount = 0, lastEmailAt = null } = $props();

  const presentation = $derived(
    getLeadEmailStatusPresentation(status, { draftCount, lastEmailAt })
  );
  const icons = {
    draft: Mail,
    sent: Send,
    replied: MessageSquare,
    follow_up: AlertCircle
  };
  const Icon = $derived(presentation ? icons[presentation.icon] : AlertCircle);
</script>

{#if presentation}
  <span
    data-email-status={status}
    class="inline-flex min-w-0 items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium {presentation.classes}"
    title={presentation.title}
  >
    <Icon class="h-3 w-3 shrink-0" />
    <span class="truncate">{presentation.label}</span>
  </span>
{/if}
