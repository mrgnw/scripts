# sk-view-transitions Project Structure

## File Tree

└── 📁 src/
    ├── 📁 lib/
    │   ├── 🟨 data.js
    │   └── 🟨 index.js
    └── 📁 routes/
        └── 📁 item/
            └── 📁 [id]/
                └── 🔥 +page.svelte
        ├── 🔥 +layout.svelte
        └── 🔥 +page.svelte
└── 🔧 package.json

## File Contents

### package.json

```json
{
  "name": "view-transitions",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "@sveltejs/adapter-auto": "^2.0.0",
    "@sveltejs/kit": "^1.20.4",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.24",
    "postcss-load-config": "^4.0.1",
    "svelte": "^4.0.5",
    "tailwindcss": "^3.3.2",
    "vite": "^4.4.2"
  },
  "type": "module"
}

```

### src/lib/data.js

```js
export default [
	{
		id: '1',
		name: 'Ethereal Serenity',
		excerpt: 'Capturing Tranquility',
		description: 'This abstract art piece captures the essence of serenity and tranquility with its soft, flowing lines and calming pastel hues. It invites viewers to a world of peaceful contemplation.',
	},
	{
		id: '2',
		name: 'Cosmic Whirlwind',
		excerpt: 'A Journey Through the Cosmos',
		description: 'A dynamic explosion of colors and shapes that resemble a cosmic whirlwind. This abstract art piece is a mesmerizing journey through the vastness of the universe.',
	},
	{
		id: '3',
		name: 'Harmony in Chaos',
		excerpt: 'Order Amidst the Chaos',
		description: 'In the midst of chaos, there is a hidden order. "Harmony in Chaos" portrays the delicate balance of structured geometry within a chaotic and vibrant backdrop.',
	},
	{
		id: '4',
		name: 'Surreal Dreamscape',
		excerpt: 'Where Reality Meets Imagination',
		description: 'Step into a surreal dreamscape where reality and imagination merge. This artwork will take you on a journey through the abstract and the extraordinary.',
	},
	{
		id: '5',
		name: 'Emerald Mirage',
		excerpt: 'Journey to a Lush Oasis',
		description: 'Emerald Mirage is a shimmering sea of emerald and turquoise, evoking the serenity of a tranquil oasis hidden in the heart of a desert. It\'s a visual escape to a lush paradise.',
	},
	{
		id: '6',
		name: 'Aurora Borealis Reverie',
		excerpt: 'Mimicking the Northern Lights',
		description: 'This abstract art piece mimics the ethereal beauty of the Northern Lights. The swirling colors and patterns create a vivid portrayal of a mystical celestial phenomenon.',
	},
	{
		id: '7',
		name: 'Metamorphosis Unleashed',
		excerpt: 'Embracing Change and Possibilities',
		description: 'Metamorphosis Unleashed is a representation of change and transformation. The vivid and bold colors symbolize the limitless possibilities that come with embracing change.',
	},
	{
		id: '8',
		name: 'Fragmented Realities',
		excerpt: 'Exploring Perceptions',
		description: 'Fragmented Realities delves into the fractured nature of our perception of the world. It explores the idea that our understanding of reality is composed of countless interconnected fragments.',
	},
];

```

### src/lib/index.js

```js
// place files you want to import through the `$lib` alias in this folder.

```

### src/routes/+layout.svelte

```svelte
<script>
	import '../app.postcss'
	import { onNavigate } from '$app/navigation'

	onNavigate((navigation) => {
		if (!document.startViewTransition) return

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve()
				await navigation.complete
			})
		})
	})
</script>

<div class="font-sans">
	<header>
		<nav class="border-b">
			<div class="container mx-auto px-6 lg:px-0 py-6">
				<a class="text-teal-700 font-medium" href="/">ZIKEA</a>
			</div>
		</nav>
	</header>
	<div class="container mx-auto px-6 lg:px-0">
		<slot />
	</div>
</div>

```

### src/routes/+page.svelte

```svelte
<script>
	import items from '$lib/data.js'
</script>

<section class="py-12">
	<div class="w-full grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6 gap-y-10">
		{#each items as item}
			<a class="item text-slate-900 hover:text-teal-700" href="/item/{item.id}">
				<img
					src={`/images/${item.id}.jpg`}
					class="object-cover rounded aspect-[4/3]"
					style={`view-transition-name: item-image-${item.id};`}
					alt={item.name}
				/>
				<h2 class="pt-4 font-semibold">{item.name}</h2>
				<p class="pt-1 text-gray-700">{item.excerpt}</p>
			</a>
		{/each}
	</div>
</section>

```

### src/routes/item/[id]/+page.svelte

```svelte
<script>
	import { page } from '$app/stores'
	import items from '$lib/data.js'

	$: id = $page.params.id

	$: item = items.find((item) => item.id === id)

	$: otherItems = items.filter((item) => item.id !== id)
</script>

<section class="py-12">
	<div class="flex flex-col lg:flex-row gap-10 lg:gap-20">
		<img
			src={`/images/${item.id}.jpg`}
			class="object-cover rounded w-full max-w-md xl:max-w-2xl aspect-[4/3]"
			style={`view-transition-name: item-image-${item.id};`}
			alt={item.name}
		/>
		<div>
			<h1 class="text-5xl font-bold tracking-tight text-slate-900">{item.name}</h1>
			<p class="mt-3 text-xl text-gray-700">{item.excerpt}</p>
			<p class="mt-6 text-gray-600 max-w-xl">{item.description}</p>
			<button
				type="button"
				disabled
				class="mt-6 text-white bg-teal-700 hover:bg-teal-800 focus:ring-4 focus:outline-none focus:ring-teal-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center inline-flex items-center mr-2 dark:bg-teal-600 dark:hover:bg-teal-700 dark:focus:ring-teal-800"
			>
				<svg
					class="w-3.5 h-3.5 mr-2"
					aria-hidden="true"
					xmlns="http://www.w3.org/2000/svg"
					fill="currentColor"
					viewBox="0 0 18 21"
				>
					<path
						d="M15 12a1 1 0 0 0 .962-.726l2-7A1 1 0 0 0 17 3H3.77L3.175.745A1 1 0 0 0 2.208 0H1a1 1 0 0 0 0 2h.438l.6 2.255v.019l2 7 .746 2.986A3 3 0 1 0 9 17a2.966 2.966 0 0 0-.184-1h2.368c-.118.32-.18.659-.184 1a3 3 0 1 0 3-3H6.78l-.5-2H15Z"
					/>
				</svg>
				Coming Soon
			</button>
		</div>
	</div>
</section>
<section class="pb-12">
	<h2 class="font-bold text-2xl text-slate-900 tracking-tight mb-12">
		Explore More From Our Collection
	</h2>
	<div class="w-full grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6 gap-y-10">
		{#each otherItems as item}
			<a class="item text-slate-900 hover:text-teal-700" href="/item/{item.id}">
				<img
					src={`/images/${item.id}.jpg`}
					class="object-cover rounded aspect-[4/3]"
					style={`view-transition-name: item-image-${item.id};`}
					alt={item.name}
				/>
				<h2 class="pt-4 font-semibold">{item.name}</h2>
				<p class="pt-1 text-gray-700">{item.excerpt}</p>
			</a>
		{/each}
	</div>
</section>

```

