Starting Container
  File "/app/bot.py", line 2134, in <module>
    bot.run(TOKEN)
    ~~~~~~~^^^^^^^
    return future.result()
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 933, in run
    asyncio.run(runner())
           ~~~~~~~~~~~~~^^
    ~~~~~~~~~~~^^^^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 922, in runner
    await self.start(token, reconnect=reconnect)
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/runners.py", line 119, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/base_events.py", line 725, in run_until_complete
[2026-07-31 22:00:43] [INFO    ] discord.client: logging in using static token
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/runners.py", line 196, in run
Traceback (most recent call last):
    return runner.run(main)
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 850, in start
    await self.login(token)
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 693, in login
           ~~~~~~~~~~^^^^^^
    await self.setup_hook()
  File "/app/bot.py", line 734, in setup_hook
    self.add_view(TicketSetupView())
                  ~~~~~~~~~~~~~~~^^
  File "/app/bot.py", line 682, in __init__
    self.add_item(ServiceTicketButton(category, row=index // 2))
                  ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/bot.py", line 661, in __init__
    super().__init__(
    ~~~~~~~~~~~~~~~~^
        label=category["label"],
        ^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
        row=row
        ^^^^^^^
    )
    ^
  File "/app/.venv/lib/python3.13/site-packages/discord/ui/button.py", line 162, in __init__
    self.row = row
    ^^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/discord/ui/item.py", line 166, in row
    raise ValueError('row cannot be negative or greater than or equal to 5')
ValueError: row cannot be negative or greater than or equal to 5
[2026-07-31 22:00:47] [INFO    ] discord.client: logging in using static token
Traceback (most recent call last):
    await self.login(token)
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 693, in login
    await self.setup_hook()
  File "/app/bot.py", line 734, in setup_hook
  File "/app/bot.py", line 2134, in <module>
    bot.run(TOKEN)
    ~~~~~~~^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 933, in run
    asyncio.run(runner())
    ~~~~~~~~~~~^^^^^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/runners.py", line 196, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/runners.py", line 119, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/base_events.py", line 725, in run_until_complete
    return future.result()
           ~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 922, in runner
    await self.start(token, reconnect=reconnect)
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 850, in start
    self.add_view(TicketSetupView())
                  ~~~~~~~~~~~~~~~^^
  File "/app/bot.py", line 682, in __init__
    self.add_item(ServiceTicketButton(category, row=index // 2))
    )
    ^
  File "/app/.venv/lib/python3.13/site-packages/discord/ui/button.py", line 162, in __init__
                  ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
    self.row = row
  File "/app/bot.py", line 661, in __init__
    ^^^^^^^^
    super().__init__(
  File "/app/.venv/lib/python3.13/site-packages/discord/ui/item.py", line 166, in row
    ~~~~~~~~~~~~~~~~^
    raise ValueError('row cannot be negative or greater than or equal to 5')
        label=category["label"],
ValueError: row cannot be negative or greater than or equal to 5
        ^^^^^^^^^^^^^^^^^^^^^^^^
[2026-07-31 22:00:50] [INFO    ] discord.client: logging in using static token
    ...<3 lines>...
Traceback (most recent call last):
        row=row
  File "/app/bot.py", line 2134, in <module>
        ^^^^^^^
    bot.run(TOKEN)
    ~~~~~~~^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 933, in run
    asyncio.run(runner())
    ~~~~~~~~~~~^^^^^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/runners.py", line 196, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/runners.py", line 119, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/mise/installs/python/3.13.14/lib/python3.13/asyncio/base_events.py", line 725, in run_until_complete
    return future.result()
           ~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 922, in runner
    await self.start(token, reconnect=reconnect)
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 850, in start
    await self.login(token)
  File "/app/.venv/lib/python3.13/site-packages/discord/client.py", line 693, in login
    await self.setup_hook()
  File "/app/bot.py", line 734, in setup_hook
