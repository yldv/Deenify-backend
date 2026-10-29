from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, Update, User

from bot.handlers import setup_routers
from bot.states import ChoosingLanguage, HelpState, SettingsState
from bot.texts import get_text


class RestartNavigationTests(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dispatcher = Dispatcher(storage=MemoryStorage())
        cls.dispatcher.include_router(setup_routers())

    async def asyncSetUp(self):
        self.bot = Bot(token="123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk")
        self.state = self.dispatcher.fsm.get_context(bot=self.bot, chat_id=123, user_id=123)
        await self.state.clear()
        self.api = SimpleNamespace(
            get_user=AsyncMock(return_value={"is_registered": True, "is_premium": True, "language": "ru",
                                            "subscription": {"status": "active", "plan": "Premium"}}),
            cancel_subscription=AsyncMock(return_value={"had_premium": False, "had_renewal": False}),
        )

    async def asyncTearDown(self):
        await self.bot.session.close()

    async def send(self, key):
        update = Update(update_id=1, message=Message(
            message_id=1, date=datetime.now(timezone.utc), chat=Chat(id=123, type="private"),
            from_user=User(id=123, is_bot=False, first_name="Test"), text=get_text("ru", key),
        ))
        with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
            await self.dispatcher.feed_update(self.bot, update, api_client=self.api)
            self.assertTrue(answer.await_count, f"No reply for stale keyboard: {key}")
            return answer

    async def test_status_and_back_work_after_memory_storage_reset(self):
        answer = await self.send("settings_subscription_status")
        self.assertEqual(await self.state.get_state(), SettingsState.menu.state)
        self.assertEqual((await self.state.get_data())["language"], "ru")
        self.assertIn("Premium", answer.call_args.args[0])
        await self.state.clear()  # Simulate another process restart.
        answer = await self.send("back")
        self.assertEqual(answer.call_args.args[0], get_text("ru", "home_menu"))
        self.assertIsNone(await self.state.get_state())

    async def test_cancel_and_language_buttons_recover_after_restart(self):
        await self.send("settings_cancel_subscription")
        self.api.cancel_subscription.assert_awaited_once()
        self.assertEqual(await self.state.get_state(), SettingsState.menu.state)
        await self.state.clear()
        await self.send("change_language")
        self.assertEqual(await self.state.get_state(), ChoosingLanguage.language.state)

    async def test_help_menu_back_still_uses_its_own_handler(self):
        await self.state.set_state(HelpState.menu)
        await self.state.update_data(language="ru")
        answer = await self.send("back")
        self.assertEqual(answer.call_args.args[0], get_text("ru", "home_menu"))
        self.assertIsNone(await self.state.get_state())
