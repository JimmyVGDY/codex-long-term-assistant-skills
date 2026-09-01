# .NET Server Rules

Confirm the target framework and SDK, solution/project files, ASP.NET Core or Worker host, EF Core, deployment model, and nullable settings. Do not mix modern .NET, legacy .NET Framework, and different ASP.NET lifecycle assumptions.

- Validate Singleton, Scoped, and Transient lifetimes. A singleton must not capture a scoped or request object.
- Do not share HttpContext or scoped DbContext across requests, background threads, or long-lived caches.
- Keep async chains asynchronous, avoid `.Result`, `.Wait()`, and unobserved fire-and-forget work, and propagate CancellationToken.
- Check BackgroundService loop, error, delay, shutdown, and scope creation.
- Review EF Core tracking, N+1, Include, concurrency tokens, transactions, migrations, and materialization.
- Use HttpClientFactory or equivalent lifecycle management with explicit timeout, retry, circuit, and idempotency behavior.
- Check authentication schemes, policies, resource authorization, anti-forgery, model binding, file upload, Data Protection, serialization, and options validation.
- Run the project's build, tests, and analyzers. Trimming, AOT, native libraries, and deployment-model changes require separate compatibility validation.
