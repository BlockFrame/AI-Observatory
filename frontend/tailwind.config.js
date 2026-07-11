/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		colors: {
			// Cybernetic Blueprint - Dark Base
			transparent: 'transparent',
			black: '#000000',
			white: '#ffffff',

			// Surface Palette
			'surface': '#131313',
			'surface-dim': '#131313',
			'surface-bright': '#3a3939',
			'surface-container-lowest': '#0e0e0e',
			'surface-container-low': '#1c1b1b',
			'surface-container': '#201f1f',
			'surface-container-high': '#2a2a2a',
			'surface-container-highest': '#353534',
			'on-surface': '#e5e2e1',
			'on-surface-variant': '#b9cac3',
			'inverse-surface': '#e5e2e1',
			'inverse-on-surface': '#313030',
			'outline': '#83948e',
			'outline-variant': '#3a4a45',
			'surface-tint': '#00e0bb',
			'surface-variant': '#353534',

			// Primary (Neon Cyan)
			'primary': '#ffffff',
			'on-primary': '#00382d',
			'primary-container': '#00ffd5',
			'on-primary-container': '#00725e',
			'inverse-primary': '#006b58',
			'primary-fixed': '#00ffd5',
			'primary-fixed-dim': '#00e0bb',
			'on-primary-fixed': '#002019',
			'on-primary-fixed-variant': '#005142',

			// Secondary (Electric Lime)
			'secondary': '#ffffff',
			'on-secondary': '#283500',
			'secondary-container': '#c3f400',
			'on-secondary-container': '#556d00',
			'secondary-fixed': '#c3f400',
			'secondary-fixed-dim': '#abd600',
			'on-secondary-fixed': '#161e00',
			'on-secondary-fixed-variant': '#3c4d00',

			// Tertiary
			'tertiary': '#ffffff',
			'on-tertiary': '#313030',
			'tertiary-container': '#e5e2e1',
			'on-tertiary-container': '#656464',
			'tertiary-fixed': '#e5e2e1',
			'tertiary-fixed-dim': '#c8c6c5',
			'on-tertiary-fixed': '#1c1b1b',
			'on-tertiary-fixed-variant': '#474746',

			// Error
			'error': '#ffb4ab',
			'on-error': '#690005',
			'error-container': '#93000a',
			'on-error-container': '#ffdad6',

			// Background
			'background': '#131313',
			'on-background': '#e5e2e1',

			// Brand-specific
			'neon-cyan': '#00ffd5',
			'electric-lime': '#ccff00',
			'wireframe-gray': '#333333',
			'surface-black': '#050505',
			'ghost-white': '#f5f5f5'
		},
		fontFamily: {
			// Hanken Grotesk for main typography
			sans: ['Hanken Grotesk', 'sans-serif'],
			// JetBrains Mono for technical labels
			mono: ['JetBrains Mono', 'monospace']
		},
		fontSize: {
			// Display
			'display-hero': ['84px', { lineHeight: '90%', letterSpacing: '-0.04em', fontWeight: '800' }],
			'headline-xl': ['32px', { lineHeight: '120%', letterSpacing: '-0.015em', fontWeight: '700' }],
			'headline-lg': ['48px', { lineHeight: '110%', letterSpacing: '-0.02em', fontWeight: '700' }],
			'headline-lg-mobile': ['32px', { lineHeight: '110%', fontWeight: '700' }],
			'headline-md': ['32px', { lineHeight: '120%', fontWeight: '600' }],
			'body-lg': ['18px', { lineHeight: '160%', fontWeight: '400' }],
			'body-md': ['16px', { lineHeight: '160%', fontWeight: '400' }],
			'body-sm': ['14px', { lineHeight: '150%', fontWeight: '400' }],
			'label-caps': ['14px', { lineHeight: '140%', letterSpacing: '0.1em', fontWeight: '600' }],
			'label-mono': ['14px', { lineHeight: '140%', letterSpacing: '0.1em', fontWeight: '500' }],
			'data-mono': ['12px', { lineHeight: '140%', letterSpacing: '0.05em', fontWeight: '500', fontFamily: 'JetBrains Mono' }],
			'caption': ['12px', { lineHeight: '140%', letterSpacing: '0.05em', fontWeight: '500' }]
		},
		spacing: {
			// Cybernetic spacing scale
			'margin-safe': '4rem',
			'gutter-grid': '1.5rem',
			'section-gap': '10rem',
			'stack-sm': '0.5rem',
			'stack-md': '1rem',
			'stack-lg': '2rem',
			// Standard TW spacing (required)
			'0': '0',
			'1': '0.25rem',
			'2': '0.5rem',
			'3': '0.75rem',
			'4': '1rem',
			'5': '1.25rem',
			'6': '1.5rem',
			'8': '2rem',
			'10': '2.5rem',
			'12': '3rem',
			'16': '4rem',
			'20': '5rem',
			'24': '6rem',
			'32': '8rem',
			'40': '10rem',
			'48': '12rem',
			'56': '14rem',
			'64': '16rem'
		},
		extend: {
			borderRadius: {
				// Sharp corners only (0px)
				'none': '0px'
			},
			boxShadow: {
				// Inner glow instead of drop shadows
				'neon-glow': 'inset 0 0 10px rgba(0, 255, 213, 0.3)',
				'lime-glow': 'inset 0 0 10px rgba(204, 255, 0, 0.3)',
				// Glassmorphism
				'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)'
			},
			backdropBlur: {
				'glass': '12px'
			},
			backgroundColor: {
				'glass': 'rgba(255, 255, 255, 0.05)'
			}
		}
	},
	plugins: [
		require('@tailwindcss/typography')
	]
};
