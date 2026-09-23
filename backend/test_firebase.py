from firebase_service import FirebaseConfigurationError, get_firebase_db


def main() -> int:
    try:
        get_firebase_db()
    except FirebaseConfigurationError as error:
        print(f"Firebase configuration incomplete: {error}")
        return 1
    except Exception:
        print("Firebase initialization failed; check the private credentials and database configuration.")
        return 1

    print("Firebase Realtime Database connection successful!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())