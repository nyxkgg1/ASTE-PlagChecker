from app.services.embedding_service import generate_embedding


def main():
    text = (
        "The aircraft was evaluated under standard atmospheric conditions."
    )

    embedding = generate_embedding(text)

    print("Embedding generated successfully.")
    print("Dimensions:", len(embedding))
    print("First five values:", embedding[:5])


if __name__ == "__main__":
    main()