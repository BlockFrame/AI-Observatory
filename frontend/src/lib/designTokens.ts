/**
 * CYBERNETIC BLUEPRINT - Design System
 * A minimalist-brutalist design system combining precision of blueprint
 * with immersive atmosphere of dark-mode terminal
 */

export const designTokens = {
  // Colors - Cybernetic Palette
  colors: {
    // Surface/Background
    surface: '#131313',
    'surface-dim': '#131313',
    'surface-bright': '#3a3939',
    'surface-container-lowest': '#0e0e0e',
    'surface-container-low': '#1c1b1b',
    'surface-container': '#201f1f',
    'surface-container-high': '#2a2a2a',
    'surface-container-highest': '#353534',
    'on-surface': '#e5e2e1',
    'on-surface-variant': '#b9cac3',
    'surface-variant': '#353534',
    'surface-black': '#050505',
    'surface-tint': '#00e0bb',

    // Primary (Neon Cyan) - Art
    'primary': '#ffffff',
    'primary-container': '#00ffd5',
    'primary-fixed': '#00ffd5',
    'primary-fixed-dim': '#00e0bb',
    'neon-cyan': '#00ffd5',

    // Secondary (Electric Lime) - Utility
    'secondary': '#ffffff',
    'secondary-container': '#c3f400',
    'secondary-fixed': '#c3f400',
    'secondary-fixed-dim': '#abd600',
    'electric-lime': '#ccff00',

    // Tertiary
    'tertiary': '#ffffff',
    'tertiary-container': '#e5e2e1',
    'tertiary-fixed': '#e5e2e1',
    'tertiary-fixed-dim': '#c8c6c5',

    // Neutral/Wireframe
    'wireframe-gray': '#333333',
    'outline': '#83948e',
    'outline-variant': '#3a4a45',
    'ghost-white': '#f5f5f5',

    // Semantic
    'error': '#ffb4ab',
    'error-container': '#93000a',
    'inverse-surface': '#e5e2e1',
    'inverse-on-surface': '#313030',
  },

  // Typography
  typography: {
    fontFamily: {
      sans: "'Hanken Grotesk', sans-serif",
      mono: "'JetBrains Mono', monospace",
    },
    scales: {
      displayHero: {
        fontSize: '84px',
        fontWeight: 800,
        lineHeight: '90%',
        letterSpacing: '-0.04em',
      },
      headlineLg: {
        fontSize: '48px',
        fontWeight: 700,
        lineHeight: '110%',
        letterSpacing: '-0.02em',
      },
      headlineLgMobile: {
        fontSize: '32px',
        fontWeight: 700,
        lineHeight: '110%',
      },
      headlineMd: {
        fontSize: '32px',
        fontWeight: 600,
        lineHeight: '120%',
      },
      bodyLg: {
        fontSize: '18px',
        fontWeight: 400,
        lineHeight: '160%',
      },
      bodyMd: {
        fontSize: '16px',
        fontWeight: 400,
        lineHeight: '160%',
      },
      labelMono: {
        fontSize: '14px',
        fontWeight: 500,
        lineHeight: '140%',
        letterSpacing: '0.1em',
      },
      caption: {
        fontSize: '12px',
        fontWeight: 500,
        lineHeight: '140%',
        letterSpacing: '0.05em',
      },
    },
  },

  // Spacing Scale
  spacing: {
    'margin-safe': '4rem', // 64px side margins
    'gutter-grid': '1.5rem', // Column gutter
    'section-gap': '10rem', // Between sections
    'stack-sm': '0.5rem', // 8px
    'stack-md': '1rem', // 16px
    'stack-lg': '2rem', // 32px
  },

  // Breakpoints
  breakpoints: {
    mobile: '0px',
    tablet: '768px',
    desktop: '1280px',
  },

  // Grid System
  grid: {
    desktop: 12,
    tablet: 8,
    mobile: 1,
    containerWidth: '1200px',
  },

  // Effects
  effects: {
    // Glassmorphism
    glassmorphism: {
      backdrop: 'blur(12px)',
      background: 'rgba(255, 255, 255, 0.05)',
    },
    // Inner glow (neon accent)
    neonGlow: {
      boxShadow: 'inset 0 0 10px rgba(0, 255, 213, 0.3)',
    },
    // Electric lime glow
    limeGlow: {
      boxShadow: 'inset 0 0 10px rgba(204, 255, 0, 0.3)',
    },
    // Wireframe border
    wireframeBorder: '1px solid #333333',
    // Neon border
    neonBorder: '1px solid #00ffd5',
    // No rounding - all corners 90 degrees
    borderRadius: '0px',
  },

  // Component Patterns
  components: {
    // Cards
    card: {
      base: {
        background: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid #333333',
        backdropFilter: 'blur(12px)',
        padding: '1.5rem',
      },
      hover: {
        border: '1px solid #00ffd5',
        boxShadow: 'inset 0 0 10px rgba(0, 255, 213, 0.3)',
      },
      active: {
        border: '1px solid #00ffd5',
      },
    },

    // Buttons - Ghost Style
    button: {
      ghost: {
        base: {
          padding: '0.75rem 1.5rem',
          border: '1px solid #f5f5f5',
          background: 'transparent',
          color: '#f5f5f5',
          fontWeight: 500,
        },
        hover: {
          background: '#f5f5f5',
          color: '#050505',
        },
      },
      ghostPrimary: {
        base: {
          border: '1px solid #00ffd5',
          color: '#00ffd5',
        },
        hover: {
          background: '#00ffd5',
          color: '#050505',
        },
      },
      ghostSecondary: {
        base: {
          border: '1px solid #ccff00',
          color: '#ccff00',
        },
        hover: {
          background: '#ccff00',
          color: '#050505',
        },
      },
    },

    // Input Fields - Blueprint Line
    input: {
      base: {
        padding: '0.5rem 0',
        border: 'none',
        borderBottom: '1px solid #333333',
        background: 'transparent',
        color: '#e5e2e1',
        fontFamily: "'Hanken Grotesk', sans-serif",
        fontSize: '16px',
      },
      focus: {
        borderBottomColor: '#00ffd5',
        outline: 'none',
        boxShadow: 'none',
      },
    },

    // Labels - Monospaced Technical
    label: {
      base: {
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '14px',
        fontWeight: 500,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: '#b9cac3',
      },
      active: {
        color: '#00ffd5',
      },
      utility: {
        color: '#ccff00',
      },
    },

    // Chips/Tags
    chip: {
      base: {
        padding: '0.25rem 0.75rem',
        border: '1px solid #333333',
        background: 'transparent',
        color: '#e5e2e1',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '14px',
        fontWeight: 500,
        letterSpacing: '0.1em',
        borderRadius: '0px',
      },
      active: {
        border: '1px solid #00ffd5',
        color: '#00ffd5',
      },
      success: {
        border: '1px solid #ccff00',
        color: '#ccff00',
      },
      error: {
        border: '1px solid #ffb4ab',
        color: '#ffb4ab',
      },
    },
  },

  // Z-Index Scale
  zIndex: {
    base: 0,
    dropdown: 100,
    sticky: 200,
    fixed: 300,
    modal: 400,
    tooltip: 500,
  },

  // Animations
  animations: {
    duration: {
      fast: '150ms',
      normal: '200ms',
      slow: '300ms',
    },
    easing: {
      easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
      easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
      easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
    },
  },
};

/**
 * Design System Principles
 * 
 * 1. MINIMALIST-BRUTALIST HYBRID
 *    - Precision of blueprint + dark-mode terminal atmosphere
 *    - Sharp corners (0px border-radius)
 *    - Wireframe borders for structure
 *    - Neon accents for hierarchy
 * 
 * 2. COLOR HIERARCHY
 *    - Neon Cyan (#00ffd5) = Primary actions & critical data ("Art")
 *    - Electric Lime (#ccff00) = Utility functions & success states ("Utility")
 *    - Wireframe Gray (#333333) = Structural borders & inactive elements
 *    - Ghost White (#f5f5f5) = High-contrast text & secondary accents
 * 
 * 3. TYPOGRAPHY
 *    - Hanken Grotesk = Main typography (sharp, contemporary)
 *    - JetBrains Mono = Technical labels & metadata (developer-centric)
 *    - Tight leading for headings (architectural feel)
 *    - Generous line height for body (dark-mode fatigue prevention)
 * 
 * 4. ELEVATION & DEPTH
 *    - No drop shadows
 *    - Tonal layering via surfaces
 *    - Technical outlines (1px borders)
 *    - Glassmorphism for floating layers
 *    - Inner glows for neon emitting effect
 * 
 * 5. SPACING
 *    - 4rem side margins (safe zones)
 *    - 10rem between sections (immersive rhythm)
 *    - 1.5rem column gutters
 *    - Rigid alignment to grid
 * 
 * 6. COMPONENT PATTERNS
 *    - Buttons: Ghost style with borders
 *    - Cards: Transparent + wireframe border + glassmorphism
 *    - Inputs: Bottom-border only (blueprint lines)
 *    - Labels: Monospaced, all-caps, wide spacing
 *    - Chips: Rectangular blocks with borders
 */
