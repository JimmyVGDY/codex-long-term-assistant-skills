# Frontend design workflow

## Applicability

Read when building a page, changing information structure, or reshaping visual design and interaction. Logic fixes, backend-only work, and a single label change do not automatically trigger visual exploration. Existing design systems and explicit user direction take precedence. A reference example does not justify replacing frameworks, component libraries, themes, or fonts.

## Ground direction in content and tasks

Establish users, primary tasks, real content, actions, target devices, and components/styles to retain. When material is sufficient, make reasonable choices without asking about every preference. Identify placeholder copy when necessary; decorative slogans do not replace product information.

Use the [design brief](../assets/templates/design-brief.md) for complex pages; a paragraph is enough for simple work. Connect these choices to concrete requirements:

- Hierarchy: the task supported first and secondary information;
- Layout: reading order, density, alignment, responsive changes, and real long text;
- Typography/color: existing project tokens, or explicit roles and contrast for a new product;
- Interaction: primary actions, feedback, loading, empty, error, and permission states;
- Motion: explain state changes without obstructing reading, respecting reduced motion.

Compare a few sketches or textual wireframes only when a meaningful layout choice exists. Decoration, gradients, corners, colors, and fonts have no universal cross-project bans. Reuse or compatibly extend existing components before duplicating their appearance.

## Implement and inspect rendering

Check whether the proposal is a generic layout unrelated to the content before implementation. Use the project's stack, semantic HTML, components, and available assets. New assets require appropriate sources and authorization; do not introduce tracking or paid assets by default.

Inspect actual desktop/mobile rendering, wrapping, overflow, density, hierarchy, focus, contrast, and applicable states. Use [browser acceptance](browser-validation.md) for interactions and screenshots; a build is not visual or interaction evidence.

Screenshots expose concrete problems; “looks good” is not a criterion. Explain which task or content relationship a revision improves. Preserve user direction on subjective differences rather than automatically treating them as release blockers.

## Delivery

Provide the actual page or runnable entry point, concise design rationale, tested sizes/states, and unverified scope. Report visual quality separately from functional correctness. One desktop screenshot does not establish coverage of all devices.
