<!-- Options in a pressed-in tray: the selected one is pushed in and lit. -->
<script lang="ts" generics="T extends string">
	let { value = $bindable(), options }: { value: T; options: { value: T; label: string }[] } =
		$props();
</script>

<div class="tray" role="radiogroup">
	{#each options as option (option.value)}
		{@const active = value === option.value}
		<button
			type="button"
			role="radio"
			aria-checked={active}
			class="key px-3.5 py-1.5 {active ? 'key-active' : ''}"
			onclick={() => (value = option.value)}
		>
			{option.label}
		</button>
	{/each}
</div>
