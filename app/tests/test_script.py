import asyncio
from app.services.script_generator import generate_script

async def test_scripts():
    print("--- Testing Script Generation ---")
    for lang in ["bn", "hi", "en"]:
        res = await generate_script(language=lang, topic="auto")
        print(f"\n[Language: {lang.upper()}]")
        print(f"Topic: {res['topic']}")
        print(f"Script: {res['script']}")
        assert len(res['script']) > 10, "Script text is too short!"

if __name__ == "__main__":
    asyncio.run(test_scripts())

