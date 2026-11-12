<!-- A slider with its label and value readout. -->
<script lang="ts">
	let {
		value = $bindable(),
		label,
		min,
		max,
		step,
		format = (v: number) => String(v)
	}: {
		value: number;
		label: string;
		min: number;
		max: number;
		step: number;
		format?: (v: number) => string;
	} = $props();

	const fill = $derived(`${((value - min) / (max - min)) * 100}%`);
</script>

<label class="block">
	<span class="flex items-baseline justify-between">
		<span class="label">{label}</span>
		<span class="text-xs font-strong text-accent tabular-nums">{format(value)}</span>
	</span>
	<input type="range" {min} {max} {step} bind:value class="fader" style:--fill={fill} />
</label>
