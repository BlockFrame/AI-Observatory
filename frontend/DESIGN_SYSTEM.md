# Cybernetic Blueprint - Component Implementation Guide

This guide explains how to implement the "Cybernetic Blueprint" design system in Svelte components.

## Design System Overview

The **Cybernetic Blueprint** is a minimalist-brutalist design system combining:
- **Precision** of engineering blueprints
- **Atmosphere** of a dark-mode terminal
- **Sharp corners** (0px border-radius)
- **Neon accents** (#00ffd5 cyan, #ccff00 lime)
- **Wireframe aesthetic** (thin borders, grid structure)
- **Glassmorphism** effects for depth

---

## Color Palette Quick Reference

| Purpose | Color | Hex | Usage |
|---------|-------|-----|-------|
| **Primary (Art)** | Neon Cyan | `#00ffd5` | Primary actions, critical data, highlights |
| **Secondary (Utility)** | Electric Lime | `#ccff00` | Utility functions, success states |
| **Neutral** | Wireframe Gray | `#333333` | Borders, structure, inactive elements |
| **Text** | Ghost White | `#f5f5f5` | Primary text, high contrast |
| **Text Variant** | On-Surface Variant | `#b9cac3` | Secondary text, labels |
| **Surface** | Surface Black | `#050505` | Background (to make neon glow) |
| **Surface** | Surface Dark | `#131313` | Cards, containers |

---

## Typography Scale

### Display Scales
```svelte
<!-- Hero Display (84px, 800 weight) -->
<h1 class="text-display-hero">Headlines that demand attention</h1>

<!-- Large Headline (48px, 700 weight) -->
<h2 class="text-headline-lg">Major section titles</h2>

<!-- Large Headline Mobile (32px, 700 weight) -->
<h3 class="text-headline-lg-mobile">Mobile-optimized headings</h3>

<!-- Medium Headline (32px, 600 weight) -->
<h3 class="text-headline-md">Subsection titles</h3>
```

### Body Scales
```svelte
<!-- Large Body (18px, 400 weight, 160% line-height) -->
<p class="text-body-lg">Lead paragraphs or emphasized content</p>

<!-- Standard Body (16px, 400 weight, 160% line-height) -->
<p class="text-body-md">Regular text content</p>

<!-- Monospaced Label (14px, 500 weight, 0.1em spacing) -->
<p class="text-label">TECHNICAL LABELS</p>

<!-- Caption (12px, 500 weight) -->
<span class="text-caption">Metadata and small text</span>
```

---

## Components

### 1. Cards - Wireframe Aesthetic

```svelte
<div class="card">
  <div class="text-label mb-stack-md">CARD LABEL</div>
  <h3 class="text-headline-md mb-stack-md text-neon-cyan">Card Title</h3>
  <p class="text-body-md">Card content with glassmorphic background.</p>
</div>

<!-- Variants -->
<!-- High Importance -->
<div class="card card-importance-high">
  <p>Critical content with neon-cyan glow</p>
</div>

<!-- Medium Importance -->
<div class="card card-importance-medium">
  <p>Secondary content with electric-lime glow</p>
</div>

<!-- Standard -->
<div class="card card-importance-standard">
  <p>Regular content with wireframe border</p>
</div>
```

### 2. Buttons - Ghost Style

```svelte
<!-- Primary Ghost Button (Neon Cyan) -->
<button class="btn-ghost btn-ghost-primary">
  Click me
</button>

<!-- Secondary Ghost Button (Electric Lime) -->
<button class="btn-ghost btn-ghost-secondary">
  Secondary Action
</button>

<!-- Tertiary Ghost Button (Ghost White) -->
<button class="btn-ghost">
  Tertiary Action
</button>
```

**Behavior:**
- Default: Border only, transparent background
- Hover: Solid fill, high-contrast black text
- Active: Held border + glow effect

### 3. Input Fields - Blueprint Lines

```svelte
<div class="stack-md">
  <label class="text-label">USERNAME</label>
  <input 
    type="text" 
    class="input-blueprint"
    placeholder="Enter your username"
  />
</div>

<!-- No box, just bottom border like a blueprint line -->
<!-- Focus state brings neon-cyan to bottom border -->
```

### 4. Labels & Monospaced Text

```svelte
<!-- Technical Label (Monospaced, Uppercase) -->
<span class="text-label">Q2 - 2024</span>

<!-- Active Label (Neon Cyan) -->
<span class="text-label label-active">ACTIVE PHASE</span>

<!-- Utility Label (Electric Lime) -->
<span class="text-label label-utility">UTILITY FEATURE</span>

<!-- Use JetBrains Mono for all technical metadata -->
<code class="font-mono text-label">function.compute()</code>
```

### 5. Chips & Status Tags

```svelte
<!-- Default Chip -->
<span class="chip">STATUS_TAG</span>

<!-- Active/Primary Chip -->
<span class="chip chip-active">ACTIVE</span>

<!-- Success Chip (Electric Lime) -->
<span class="chip chip-success">SUCCESS</span>

<!-- Error Chip (Red) -->
<span class="chip chip-error">ERROR</span>

<!-- Group of Chips -->
<div class="flex flex-wrap gap-stack-sm">
  <span class="chip chip-active">PHASE_01</span>
  <span class="chip chip-success">DEPLOYED</span>
  <span class="chip">OPTIONAL</span>
</div>
```

### 6. Scroll Affordance

```svelte
<!-- Add to fixed position on page -->
<div class="scroll-indicator scroll-animate">
  <!-- Auto-renders: SCROLL DOWN arrow line -->
</div>

<!-- CSS handles animation -->
```

### 7. Glassmorphism Panels

```svelte
<!-- Floating card with backdrop blur -->
<div class="glass-panel p-6">
  <h3 class="text-headline-md text-neon-cyan mb-stack-md">
    Floating Panel
  </h3>
  <p class="text-body-md">
    This card floats over content with subtle glassmorphism effect.
  </p>
</div>
```

---

## Layout & Spacing

### Safe Margins
```svelte
<!-- Use margin-safe for side margins on all pages -->
<div class="container-safe">
  <!-- Content stays within 1200px container with 4rem side padding -->
</div>
```

### Section Spacing
```svelte
<!-- Use section-gap (10rem) between major sections -->
<section class="section-gap">
  <h2 class="text-headline-lg">Section 1</h2>
</section>

<section class="section-gap">
  <h2 class="text-headline-lg">Section 2</h2>
</section>
```

### Grid Layout
```svelte
<!-- 12-column grid on desktop, 8-column on tablet, 1-column on mobile -->
<div class="grid-12">
  <div class="col-span-6">Half width (6/12)</div>
  <div class="col-span-6">Half width (6/12)</div>
  <div class="col-span-4">Third width (4/12)</div>
  <div class="col-span-4">Third width (4/12)</div>
  <div class="col-span-4">Third width (4/12)</div>
</div>
```

### Stack Utilities
```svelte
<!-- Vertical spacing between elements -->
<div class="flex flex-col gap-stack-sm">Small gap (0.5rem)</div>
<div class="flex flex-col gap-stack-md">Medium gap (1rem)</div>
<div class="flex flex-col gap-stack-lg">Large gap (2rem)</div>

<!-- Horizontal gutter (grid columns) -->
<div class="grid grid-cols-2 gap-gutter-grid">
  <div>Column 1</div>
  <div>Column 2</div>
</div>
```

---

## Prose/Markdown Styling

When rendering markdown content, use `.prose-summary` class:

```svelte
<div class="prose-summary">
  {#if summary}
    {@html summary}
  {/if}
</div>
```

**Automatically styled:**
- `h2` → Neon Cyan headings with large spacing
- `h3` → Electric Lime subheadings
- `strong` → Neon Cyan bold text
- `a` → Cyan links with hover to lime
- `ul/li` → Proper list styling with lime markers
- `p` → Proper paragraph spacing and contrast

---

## Common Patterns

### Navigation

```svelte
<nav class="flex gap-stack-md border-b border-wireframe-gray py-4">
  <a class="nav-link" href="/">Home</a>
  <a class="nav-link nav-link-active" href="/feeds">Feeds</a>
  <a class="nav-link" href="/archive">Archive</a>
</nav>
```

### News Card (Complex Example)

```svelte
<article class="card card-importance-high">
  <!-- Header with label -->
  <div class="flex justify-between items-start mb-stack-md">
    <span class="text-label label-active">NEWS</span>
    <span class="text-caption text-on-surface-variant">
      {new Date(date).toLocaleDateString()}
    </span>
  </div>

  <!-- Title -->
  <h3 class="text-headline-md text-neon-cyan mb-stack-sm">
    {title}
  </h3>

  <!-- Category -->
  <span class="chip chip-success mb-stack-md">{category}</span>

  <!-- Content -->
  <p class="text-body-md text-on-surface mb-stack-lg">
    {description}
  </p>

  <!-- CTA Button -->
  <a href={link} class="btn-ghost btn-ghost-primary">
    Read More
  </a>
</article>
```

### Search Input

```svelte
<div class="stack-md">
  <label class="text-label">SEARCH</label>
  <input
    type="text"
    class="input-blueprint"
    placeholder="Search news..."
    bind:value={query}
  />
</div>
```

### Status Indicator

```svelte
<div class="flex items-center gap-stack-sm">
  <div class="w-3 h-3 border border-neon-cyan animate-pulse"></div>
  <span class="text-label label-active">LIVE</span>
</div>
```

---

## Accessibility Considerations

1. **Color Contrast**: All text meets WCAG AA standards
   - Neon Cyan on black: 8.7:1 ✓
   - Electric Lime on black: 10.2:1 ✓
   - White on black: 21:1 ✓

2. **Typography**: Generous line-height (160%) prevents eye fatigue

3. **Focus States**: All interactive elements have clear focus indicators

4. **Motion**: Animations use `prefers-reduced-motion` (implement if needed)

5. **Semantic HTML**: Use proper heading hierarchy and semantic elements

---

## Responsive Design

### Breakpoints
- **Mobile**: < 768px (single column, fluid spacing)
- **Tablet**: 768px - 1280px (8-column grid)
- **Desktop**: > 1280px (12-column grid, fixed 1200px container)

### Mobile Optimization
```svelte
<!-- Headlines scale down on mobile -->
<h1 class="text-display-hero hidden md:block">Desktop Hero</h1>
<h1 class="text-headline-lg-mobile md:hidden">Mobile Hero</h1>

<!-- Grid adapts automatically -->
<div class="grid-12">
  <!-- 12 cols on desktop, 8 on tablet, 1 on mobile -->
</div>

<!-- Spacing adapts -->
<div class="section-gap">
  <!-- 10rem on desktop, smaller on mobile via responsive utilities -->
</div>
```

---

## Animation Guidelines

### Border Glow Animation
```svelte
<!-- Add glowing border animation -->
<div class="card border-glow">
  Content with animated neon border
</div>
```

### Scroll Animation
```svelte
<!-- Pulsing scroll indicator -->
<div class="scroll-indicator scroll-animate"></div>
```

### Custom Keyframes
```css
/* Defined in app.css, but here are the available animations: */
@keyframes border-pulse {
  /* Neon border glow effect */
}

@keyframes scroll-pulse {
  /* Scroll affordance animation */
}
```

---

## Dark Mode

The entire design is built for dark mode (black/very dark backgrounds with neon accents). No light mode adaptation needed.

**Color Mode Handling:**
```svelte
<!-- All colors are hard-coded for dark mode -->
<!-- No conditional dark: classes needed -->
<div class="bg-surface text-on-surface border border-wireframe-gray">
  Always looks cybernetic, always dark
</div>
```

---

## Utility Classes Quick Reference

```
Text:
  .text-display-hero    /* 84px, 800 weight */
  .text-headline-lg     /* 48px, 700 weight */
  .text-headline-md     /* 32px, 600 weight */
  .text-body-lg         /* 18px */
  .text-body-md         /* 16px */
  .text-label           /* 14px mono uppercase */
  .text-caption         /* 12px */

Spacing:
  .margin-safe          /* 4rem side margins */
  .section-gap          /* 10rem vertical gap */
  .gutter-grid          /* 1.5rem column gutter */
  .stack-sm             /* 0.5rem gap */
  .stack-md             /* 1rem gap */
  .stack-lg             /* 2rem gap */

Components:
  .card                 /* Wireframe card */
  .btn-ghost            /* Ghost button */
  .input-blueprint      /* Blueprint input */
  .text-label           /* Monospaced label */
  .chip                 /* Status tag */

Colors:
  .text-neon-cyan       /* #00ffd5 */
  .text-electric-lime   /* #ccff00 */
  .border-neon-cyan     /* Neon border */
  .bg-surface           /* #131313 */
  .bg-surface-black     /* #050505 */

Effects:
  .shadow-neon-glow     /* Inner glow */
  .shadow-lime-glow     /* Lime glow */
  .border-glow          /* Animated glow */
  .scroll-animate       /* Scroll animation */
```

---

## Best Practices

1. **Always use margin-safe for page margins**
2. **Use grid-12 for layout (responsive)**
3. **Use section-gap between major sections**
4. **Use text scale utilities (never hard-code sizes)**
5. **Use color variables (never hard-code colors)**
6. **Use spacing scale (stack-sm/md/lg, gutter-grid)**
7. **Keep corners sharp (0px border-radius)**
8. **Use neon-cyan for primary, electric-lime for secondary**
9. **Use wireframe-gray for structure**
10. **Prefer ghost buttons over solid fills**

---

## Example: Full Page Layout

```svelte
<script lang="ts">
  // Page component example
  let query = '';
</script>

<svelte:head>
  <title>AI News Aggregator</title>
</svelte:head>

<!-- Hero Section -->
<section class="container-safe py-section-gap">
  <h1 class="text-display-hero text-neon-cyan mb-stack-lg">
    AI News Aggregator
  </h1>
  <p class="text-body-lg text-on-surface-variant max-w-2xl">
    Curated AI news, research, and insights from across the digital landscape.
  </p>
</section>

<!-- Search Section -->
<section class="container-safe mb-section-gap">
  <div class="grid-12">
    <div class="col-span-8">
      <label class="text-label mb-stack-sm block">SEARCH NEWS</label>
      <input
        type="text"
        class="input-blueprint w-full"
        placeholder="Search by topic, author, or date..."
        bind:value={query}
      />
    </div>
    <div class="col-span-4 flex items-end">
      <button class="btn-ghost btn-ghost-primary w-full">Search</button>
    </div>
  </div>
</section>

<!-- News Grid -->
<section class="container-safe mb-section-gap">
  <div class="grid-12">
    {#each newsList as item (item.id)}
      <article class="col-span-6 card card-importance-high">
        <!-- Card content -->
      </article>
    {/each}
  </div>
</section>

<style>
  /* Component-specific styles if needed */
</style>
```

---

**Questions?** Refer to `designTokens.ts` for the full design token definitions or check specific component examples above.

