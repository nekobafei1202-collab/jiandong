"""Smoke: splash → login → shell → every tab + dialogs (desktop Flet window)."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import flet as ft

from jiandong_ai.app.constants import MOCK_EMAIL, MOCK_PASSWORD
from jiandong_ai.main import main
from jiandong_ai.pages.auth.login_page import build_login
from jiandong_ai.pages.auth.register_page import build_register
from jiandong_ai.pages.home.plan_editor_page import open_plan_editor
from jiandong_ai.pages.shell import MainShell
from jiandong_ai.services.mock_service import MockService


def smoke(page: ft.Page) -> None:
    errors: list[str] = []

    def catch(label: str, fn) -> None:
        try:
            fn()
            print("OK", label, flush=True)
        except Exception as e:
            errors.append(f"{label}: {e}")
            traceback.print_exc()
            print("BAD", label, e, flush=True)

    catch("main_splash", lambda: main(page, preview=False))

    def do_register() -> None:
        page.controls.clear()
        page.add(build_register(page, on_success=lambda: None, on_back=lambda: None))
        page.update()

    catch("register_page", do_register)

    def do_login_shell() -> None:
        page.controls.clear()
        page.add(
            build_login(
                page,
                on_success=lambda: None,
                on_register=lambda: None,
            )
        )
        page.update()
        user = MockService.instance().login(MOCK_EMAIL, MOCK_PASSWORD)
        if user is None:
            raise RuntimeError("mock login failed")
        page.controls.clear()
        page.add(MainShell(page))
        page.update()

    catch("login→MainShell", do_login_shell)

    shell = next((c for c in page.controls if isinstance(c, MainShell)), None)
    if shell is None:
        errors.append("MainShell missing after login")
    else:
        for i, name in enumerate(["home", "course", "training", "records", "profile"]):
            catch(f"tab:{name}", lambda idx=i: shell._show(idx))

        course = shell._views[1]
        courses = course._svc.get_courses("全部")  # type: ignore[attr-defined]
        if courses:
            catch("course_detail", lambda: course._open_detail(courses[0]))  # type: ignore[attr-defined]
            catch("course_close", lambda: page.pop_dialog())

        catch("plan_editor", lambda: open_plan_editor(page, on_saved=lambda: None))
        catch("plan_editor_close", lambda: page.pop_dialog())

        profile = shell._views[4]
        catch("profile_logout_snack", lambda: profile._logout(None))  # type: ignore[attr-defined]

        training = shell._views[2]
        catch("training_set_action", lambda: training.set_action("俯卧撑"))  # type: ignore[attr-defined]
        catch("training_on_show", lambda: training.on_show())  # type: ignore[attr-defined]

    try:
        page.window.destroy()
    except Exception:
        try:
            page.window.close()
        except Exception:
            pass

    if errors:
        print("\n=== SMOKE ERRORS ===", flush=True)
        for e in errors:
            print("-", e, flush=True)
        # Force process exit; window destroy alone may not end ft.run
        raise SystemExit(1)
    print("\nSMOKE PASS: splash→login→register→shell→all tabs", flush=True)
    raise SystemExit(0)


if __name__ == "__main__":
    ft.run(smoke, assets_dir=str(ROOT / "assets"))
