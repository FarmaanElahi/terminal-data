try:
    from dotenv import load_dotenv

    # Load .env file at the start of testing
    load_dotenv()
except ImportError:
    pass
