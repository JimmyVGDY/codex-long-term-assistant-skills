# Browser acceptance workflow

## Choose an entry point

Use for actual frontend behavior, layout, or interaction validation. Read project test/service entry points and the host's supported browser tools. Reuse existing tests and obey tool-access rules; do not bypass them through another driver, debug port, or hidden state.

Read-only analysis does not automatically authorize starting or restarting services. Before forms, payments, messages, or other business side effects, establish environment and current authorization; prefer synthetic data and isolated services.

## Establish service and page readiness

1. Record URL, service identity, version/build, environment, and expected page. Identify existing services before acting; port occupation is not permission to kill or replace them.
2. Start only when required, using the project's real entry point. Record working directory, arguments, process/child ownership, and bounded logs, waits, and execution time. Pass arguments as arrays.
3. A listening port is a clue, not identity. Confirm the intended service through known health responses, page content, or version markers.
4. Assert target elements, data state, or business readiness. Persistent connections/background requests need not reach network idle; fixed delays are not readiness assertions.

## Observe, act, and assert

Discover controls and locators from rendered DOM or screenshots instead of guessing unseen selectors. Prefer semantic roles/stable labels and wait for observable state changes after actions.

Select normal, loading, empty, error, disabled, duplicate-action, cancellation, refresh, navigation, and race cases according to the change. Assert UI and relevant business state. A screenshot or visible button does not prove saving or authorization works. Distinguish mocks, real browser interactions, and real backend integration.

Keep the [frontend validation matrix](../assets/templates/FRONTEND_VALIDATION_MATRIX.template.md) and add the [browser evidence supplement](../assets/templates/browser-evidence.md) when browser acceptance applies. The supplement adds identity, readiness, actions, results, and resource ownership; the old matrix remains useful without browser work.

## Failure, cancellation, and cleanup

Preserve useful sanitized errors, screenshots, and reproduction steps without full cookies, credentials, sensitive forms, or unrelated network responses. Distinguish application failures, environment readiness, tool-permission denials, and incomplete execution. Unexecuted scenarios cannot pass.

Normal exit, failure, and cancellation release only browser contexts, services, and children created by this run. Never kill user services merely by name or port. Report unknown ownership and remaining resources. Verify Windows paths/process handling on the actual host rather than substituting another platform's results.

Retest affected cases after changes; do not retry indefinitely without new evidence. Distinguish build, browser, backend integration, device coverage, and unverified scope in delivery.

## Maintainer synthetic fixture

The repository's tests/fixtures/quality_browser.py supplies a public synthetic page. Use the existing Python runtime with --lease <existing-external-directory/run-lease.json> --lifetime 600. It binds loopback only, assigns separate random frontend/API ports and returns instance, role and process identity. Match health responses to that identity before opening the page. Cover static content, normal/empty/failed requests, slow-request cancellation and duplicate submission.

Run the same script with --lease <original-lease> --stop only for the lease created by this run. It verifies instance and process identity before stopping its own service. Do not display or copy the lease's owner_token. Keep existing services running. Another synthetic service establishes only that isolation case, not actual user-service acceptance. The helper does not install dependencies, take over project services or establish production-backend acceptance.
