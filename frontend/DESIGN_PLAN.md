# Dhago Design Plan

## Subject Definition
**Product**: Autonomous credit and lending system for Nepal's informal sector
**Audience**: Small business owners, farmers, and individuals in Nepal seeking quick, fair lending decisions
**Single Job**: Convince visitors that Dhago is a trustworthy, modern, and efficient alternative to traditional banks

## Design Principles
- **Cultural Grounding**: Use Nepal's rich visual heritage (Mandala patterns, traditional colors) to create instant recognition
- **Trust Through Design**: Professional, clean layout that conveys reliability without feeling cold
- **Distinctive Identity**: One memorable visual element that sets this apart from generic fintech designs

## Color Palette

| Name | Hex | Use |
|------|-----|-----|
| **Indigo Deep** | #1E3A5F | Primary brand, trust, stability |
| **Saffron** | #FF9933 | Accent, energy, Nepal cultural connection |
| **Forest** | #2D5A27 | Success states, growth |
| **Warm Gray** | #F5F3F0 | Backgrounds, warmth |
| **Charcoal** | #2C2C2C | Text, contrast |
| **Clean White** | #FFFFFF | Cards, breathing space |

**Why these colors**: The indigo represents the stability and trust needed in financial services. Saffron is drawn directly from Nepal's flag and cultural identity, creating immediate local recognition. Forest green represents growth and prosperity — what lending enables.

## Typography

| Role | Typeface | Weight | Use |
|------|----------|--------|-----|
| **Display** | DM Serif Display | 400 | Headlines, hero text |
| **Body** | Plus Jakarta Sans | 400, 500, 600 | Paragraphs, UI text |
| **Utility** | JetBrains Mono | 400, 500 | Numbers, data, IDs |

**Why these fonts**: DM Serif Display has elegant, distinctive serifs that feel premium without being stuffy. Plus Jakarta Sans is modern and highly readable. JetBrains Mono adds technical credibility for financial data.

## Layout Concept

### Hero Section
- **Asymmetric layout**: Large statistic on left (e.g., "3-5 min approval"), Mandala pattern on right
- **Background**: Warm gray (#F5F3F0) — NOT dark navy
- **Mandala**: Self-drawing SVG animation on page load
- **Stats panel**: Translucent glass effect with key metrics

### Features Section
- **Cards with top accent line**: Each card has a thin colored line at top (navy, saffron, forest)
- **Icons**: Custom line icons with cultural touches
- **Hover state**: Accent line becomes more prominent

### How It Works
- **Horizontal steps**: Connected by a gradient line (navy → saffron → forest)
- **Step indicators**: Rounded squares with gradient fills
- **Visual flow**: Arrow or line connecting steps

### CTA Section
- **Full-width**: Indigo Deep background
- **Pattern overlay**: Slowly rotating Mandala
- **Clear action**: Saffron accent button

### Footer
- **Dark background**: Charcoal with subtle pattern
- **Organized sections**: Logo, links, contact info
- **Cultural touch**: Small Mandala icon

## Signature Element: Mandala Pattern

The Mandala is a traditional Nepalese design symbolizing unity, protection, and the cycle of life. In this design:

1. **Hero Background**: A large, self-drawing Mandala SVG that animates on page load
2. **Section Dividers**: Small Mandala icons between sections
3. **Card Accents**: Thin top lines with Mandala-inspired color coding
4. **Footer Icon**: Small Mandala as brand mark

**Why Mandala**: It's instantly recognizable as Nepalese, symbolizes the protection and trust needed in lending, and creates a visual identity that cannot be confused with any other fintech product.

## Aesthetic Risk

**The Risk**: Using a culturally specific pattern (Mandala) as the primary visual element in a fintech product.

**Justification**:
1. **Differentiation**: Every fintech uses abstract shapes or gradients. A Mandala is immediately distinctive.
2. **Cultural Connection**: For Nepali users, this creates instant recognition and trust.
3. **Symbolic Meaning**: Mandala represents protection and wholeness — perfect for a lending system.
4. **Visual Interest**: The intricate pattern creates visual richness without clutter.

## Implementation Notes

1. **SVG Mandala**: Simplified Mandala SVG animated with CSS `stroke-dashoffset` for draw effect
2. **Performance**: Mandala is lightweight SVG, no heavy assets
3. **Accessibility**: All animations respect `prefers-reduced-motion`
4. **Responsive**: Mandala scales appropriately on mobile
5. **Dark Mode**: Consider future dark mode with inverted Mandala colors

## Avoided Defaults

- ❌ Warm cream background (#F4F1EA) — too generic
- ❌ High-contrast serif with terracotta accent — overused
- ❌ Near-black with acid-green accent — not appropriate for trust-focused fintech
- ❌ Broadsheet newspaper layout — not suitable for this product

## Success Metrics

1. **Distinctiveness**: Can this be mistaken for another product? (No)
2. **Cultural Resonance**: Does it feel connected to Nepal? (Yes)
3. **Trust**: Does it feel professional and reliable? (Yes)
4. **Memorability**: What one element will users remember? (Mandala pattern)
