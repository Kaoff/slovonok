<!-- Development only: turn the CRT scanlines off for readability. Not shown in the build. -->
<script lang="ts">
	let crt = $state(localStorage.getItem('slovonok-crt') !== 'off');

	$effect(() => {
		document.documentElement.classList.toggle('no-crt', !crt);
		localStorage.setItem('slovonok-crt', crt ? 'on' : 'off');
	});
</script>

<button class="key w-full text-xs" onclick={() => (crt = !crt)}>
	<span class={crt ? 'led-on' : 'led'}></span>
	CRT {crt ? 'on' : 'off'} (dev)
</button>
