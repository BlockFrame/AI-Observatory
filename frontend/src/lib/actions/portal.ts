/** Move an overlay host to document.body so fixed positioning is never clipped. */
export function portal(node: HTMLElement) {
	const placeholder = document.createComment('portal');
	node.parentNode?.insertBefore(placeholder, node);
	document.body.appendChild(node);

	return {
		destroy() {
			node.remove();
			placeholder.remove();
		}
	};
}
