<script>
  /* eslint-disable svelte/no-navigation-without-resolve */

  /** @type {{ signature?: any, compact?: boolean }} */
  let { signature = null, compact = false } = $props();

  function websiteLabel(value) {
    return (value || '').replace(/^https?:\/\//, '').replace(/\/$/, '');
  }
</script>

{#if signature?.is_enabled}
  <div
    class="max-w-[600px] bg-white font-sans text-[#243229]"
    style={`--signature-primary:${signature.primary_color};--signature-accent:${signature.accent_color}`}
  >
    <p class="mb-3 text-sm leading-5">Met vriendelijke groet,</p>
    <div class="h-[3px] bg-[var(--signature-accent)]"></div>
    <div class={`grid items-start gap-4 ${compact ? 'grid-cols-1' : 'sm:grid-cols-[1fr_240px]'}`}>
      <div class="py-4">
        <div class="text-lg font-bold leading-6 text-[var(--signature-primary)]">
          {signature.sender_name}
        </div>
        {#if signature.sender_role}
          <div class="text-[13px] leading-[18px] text-gray-500">{signature.sender_role}</div>
        {/if}
        <div class="mt-2 text-[13px] font-bold leading-[18px]">{signature.company_name}</div>
        <div class="mt-1 text-[13px] leading-[19px]">
          {#if signature.phone_number}
            <a
              class="block text-[var(--signature-primary)] no-underline"
              href={`tel:${signature.phone_number}`}
            >
              {signature.phone_number}
            </a>
          {/if}
          <a
            class="block text-[var(--signature-primary)] no-underline"
            href={`mailto:${signature.email_address}`}
          >
            {signature.email_address}
          </a>
          {#if signature.website_url}
            <a
              class="block text-[var(--signature-primary)] no-underline"
              href={signature.website_url}
            >
              {websiteLabel(signature.website_url)}
            </a>
          {/if}
        </div>
        {#if signature.address}
          <div class="mt-1 text-xs leading-[17px] text-gray-500">{signature.address}</div>
        {/if}
      </div>
      {#if signature.logo_url && !compact}
        <div class="pt-[18px] sm:text-right">
          <img
            src={signature.logo_url}
            alt={signature.company_name}
            class="inline-block h-auto w-full max-w-[240px]"
          />
        </div>
      {/if}
    </div>
    {#if signature.certifications?.length}
      <div class="grid grid-cols-3 gap-1">
        {#each signature.certifications as certification (certification.name)}
          <a
            href={certification.url || undefined}
            class="flex min-h-[76px] flex-col items-center justify-center bg-[#f7f8f7] px-2 py-2 text-center no-underline"
          >
            {#if certification.image_url}
              <img
                src={certification.image_url}
                alt={certification.name}
                class="mb-1.5 h-[38px] w-auto max-w-[84px] object-contain"
              />
            {/if}
            <span class="text-[11px] leading-[15px] text-gray-600">{certification.name}</span>
          </a>
        {/each}
      </div>
    {/if}
    {#if signature.review_score && signature.review_count && signature.reviews_url}
      <div
        class="mt-2 flex flex-wrap items-center justify-between gap-x-5 gap-y-2 bg-[#f7f8f7] px-3 py-2.5"
      >
        <div class="flex flex-wrap items-center gap-x-2">
          <span class="whitespace-nowrap text-base tracking-wide text-[var(--signature-accent)]">
            ★★★★★
          </span>
          <strong class="whitespace-nowrap text-sm text-[#243229]">
            {String(signature.review_score).replace('.', ',')}/10
          </strong>
          <span class="whitespace-nowrap text-[11px] text-gray-500">
            uit {signature.review_count}+ beoordelingen
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-2 text-xs font-bold">
          <a class="text-[var(--signature-primary)] no-underline" href={signature.reviews_url}>
            Bekijk onze reviews →
          </a>
          {#if signature.projects_url}
            <span class="text-gray-300">|</span>
            <a class="text-[var(--signature-primary)] no-underline" href={signature.projects_url}>
              Bekijk onze projecten →
            </a>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{:else}
  <p class="text-sm text-[var(--text-secondary)]">Er is geen actieve e-mailhandtekening.</p>
{/if}
