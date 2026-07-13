/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		colors: {
			// Synthetic Intelligence Observatory palette
			transparent: 'transparent',
			black: '#000000',
			white: '#ffffff',

			// Surfaces
			'surface': '#0c1322',
			'surface-dim': '#0c1322',
			'surface-bright': '#323949',
			'surface-container-lowest': '#070e1d',
			'surface-container-low': '#141b2b',
			'surface-container': '#191f2f',
			'surface-container-high': '#232a3a',
			'surface-container-highest': '#2e3545',
			'on-surface': '#dce2f7',
			'on-surface-variant': '#c7c4d7',
			'inverse-surface': '#dce2f7',
			'inverse-on-surface': '#293040',
			'outline': '#908fa0',
			'outline-variant': '#464554',
			'surface-tint': '#c0c1ff',
			'surface-variant': '#2e3545',

			// Brand
			'primary': '#c0c1ff',
			'on-primary': '#1000a9',
			'primary-container': '#8083ff',
			'on-primary-container': '#0d0096',
			'inverse-primary': '#494bd6',
			'primary-fixed': '#e1e0ff',
			'primary-fixed-dim': '#c0c1ff',
			'on-primary-fixed': '#07006c',
			'on-primary-fixed-variant': '#2f2ebe',

			'secondary': '#ffb3ad',
			'on-secondary': '#68000a',
			'secondary-container': '#a40217',
			'on-secondary-container': '#ffaea8',
			'secondary-fixed': '#ffdad7',
			'secondary-fixed-dim': '#ffb3ad',
			'on-secondary-fixed': '#410004',
			'on-secondary-fixed-variant': '#930013',

			'tertiary': '#4edea3',
			'on-tertiary': '#003824',
			'tertiary-container': '#00885d',
			'on-tertiary-container': '#000703',
			'tertiary-fixed': '#6ffbbe',
			'tertiary-fixed-dim': '#4edea3',
			'on-tertiary-fixed': '#002113',
			'on-tertiary-fixed-variant': '#005236',

			// Semantic
			'error': '#ffb4ab',
			'on-error': '#690005',
			'error-container': '#93000a',
			'on-error-container': '#ffdad6',

			// Background
			'background': '#0c1322',
			'on-background': '#dce2f7',

			// Accent
			'electric-blue': '#60A5FA',

			// Legacy aliases used in components
			'trend-red': '#c0c1ff',
			'guardian-red': '#8083ff',
			'trend-dark': '#0c1322',
			'trend-gray-50': '#eef1ff',
			'trend-gray-100': '#dce2f7',
			'trend-gray-200': '#c7c4d7',
			'trend-gray-300': '#a9a8ba',
			'trend-gray-400': '#908fa0',
			'trend-gray-500': '#6f7385',
			'trend-gray-600': '#464554',
			'trend-gray-700': '#2e3545',
			'trend-gray-800': '#191f2f',
			'trend-gray-900': '#0c1322',
			'category-social': '#4edea3'
		},
		fontFamily: {
			// Hanken Grotesk for main typography
			sans: ['Hanken Grotesk', 'sans-serif'],
			// JetBrains Mono for technical labels
			mono: ['JetBrains Mono', 'monospace']
		},
		fontSize: {
			...require('tailwindcss/defaultTheme').fontSize,
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
			...require('tailwindcss/defaultTheme').spacing,
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
