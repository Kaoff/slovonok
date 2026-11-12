<!-- An on/off switch. Its look comes from the theme (switch-* utilities). -->
<script lang="ts">
	let {
		checked = $bindable(),
		label,
		hint,
		title
	}: { checked: boolean; label?: string; hint?: string; title?: string } = $props();
</script>

<!-- relative: the hidden checkbox (absolute) must stay inside the label. Otherwise it is placed
     against the body, below the fold of a scrolled column, and focusing it scrolls the whole
     (locked) page. -->
<label class="relative flex cursor-pointer items-start gap-3" {title}>
	<input type="checkbox" bind:checked class="peer sr-only" />
	<span
		class="switch-track mt-0.5 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-3 peer-focus-visible:outline-accent"
	>
		<span class="switch-knob {checked ? 'switch-knob-on' : ''}"></span>
	</span>
	{#if label || hint}
		<span class="min-w-0">
			{#if label}<span class="block text-sm font-strong">{label}</span>{/if}
			{#if hint}<span class="block text-xs text-muted">{hint}</span>{/if}
		</span>
	{/if}
</label>
