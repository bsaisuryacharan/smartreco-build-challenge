"""
Run once to populate the database and ChromaDB with demo data.
  python seed_products.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import init_db, SessionLocal
from app.models import User, Product
from app.auth import hash_password
from app.services.vector_store import upsert_product, get_vector_store

COURSES = [
    {
        "title": "Python for Data Science — Zero to Hero",
        "description": "A comprehensive guide to Python for data analysis. Covers NumPy, Pandas, Matplotlib, and real-world data wrangling workflows from raw CSV files to production-ready pipelines.",
        "category": "Data Science",
        "price": 49.99,
    },
    {
        "title": "Machine Learning with Scikit-Learn",
        "description": "Build and evaluate supervised and unsupervised ML models using scikit-learn. Includes regression, classification, clustering, and model selection with cross-validation.",
        "category": "Machine Learning",
        "price": 79.99,
    },
    {
        "title": "Deep Learning with PyTorch",
        "description": "Master neural networks from the ground up using PyTorch. Covers feedforward networks, CNNs, RNNs, and fine-tuning pre-trained models on custom datasets.",
        "category": "Deep Learning",
        "price": 99.99,
    },
    {
        "title": "Natural Language Processing with Transformers",
        "description": "Learn how to apply transformer-based models (BERT, GPT, T5) for text classification, summarization, translation, and question answering using HuggingFace.",
        "category": "NLP",
        "price": 119.99,
    },
    {
        "title": "Building Agentic AI Systems with LangChain",
        "description": "Design and deploy AI agents that use tools, memory, and multi-step reasoning. Covers LangChain agents, tool-calling, RAG pipelines, and LangGraph workflows.",
        "category": "Agentic AI",
        "price": 139.99,
    },
    {
        "title": "Computer Vision with OpenCV and PyTorch",
        "description": "From image processing fundamentals to object detection and segmentation. Build models for face recognition, YOLO-based detection, and image classification at scale.",
        "category": "Computer Vision",
        "price": 89.99,
    },
    {
        "title": "MLOps: Deploying ML Models to Production",
        "description": "Learn best practices for packaging, versioning, monitoring, and retraining ML models in production. Covers Docker, FastAPI, MLflow, and CI/CD for model deployment.",
        "category": "MLOps",
        "price": 109.99,
    },
    {
        "title": "Retrieval-Augmented Generation (RAG) — Complete Guide",
        "description": "Implement end-to-end RAG systems using vector databases, embedding models, and LLMs. Includes chunking strategies, re-ranking, evaluation, and hybrid search.",
        "category": "Agentic AI",
        "price": 129.99,
    },
    {
        "title": "Statistics for Machine Learning",
        "description": "Build a rigorous statistical foundation for ML — probability theory, Bayesian inference, hypothesis testing, and the math behind gradient descent and regularization.",
        "category": "Data Science",
        "price": 59.99,
    },
    {
        "title": "Generative AI with Stable Diffusion",
        "description": "Explore text-to-image generation, fine-tuning diffusion models, LoRA adapters, and controlnet for creative and production applications.",
        "category": "Deep Learning",
        "price": 94.99,
    },
    {
        "title": "Time Series Forecasting with Python",
        "description": "Forecast sales, stock prices, and sensor data using ARIMA, Prophet, LSTM networks, and transformer-based sequence models in Python.",
        "category": "Machine Learning",
        "price": 74.99,
    },
    {
        "title": "Reinforcement Learning — From Basics to Deep RL",
        "description": "Understand MDPs, Q-learning, policy gradients, and PPO. Train agents to master Atari games and continuous control tasks using Gymnasium and Stable-Baselines3.",
        "category": "Deep Learning",
        "price": 114.99,
    },
    {
        "title": "LLM Fine-Tuning and Prompt Engineering",
        "description": "Learn PEFT, LoRA, and QLoRA techniques to fine-tune large language models on custom datasets. Also covers prompt chaining, few-shot prompting, and structured output.",
        "category": "NLP",
        "price": 149.99,
    },
    {
        "title": "Vector Databases and Semantic Search",
        "description": "Deep dive into Pinecone, Chroma, Weaviate, and Qdrant. Build production-grade semantic search engines with hybrid retrieval and metadata filtering.",
        "category": "Agentic AI",
        "price": 84.99,
    },
    {
        "title": "Data Engineering with Apache Spark and Kafka",
        "description": "Build real-time and batch data pipelines using Spark, Kafka, and Delta Lake. Covers distributed computing fundamentals and streaming architecture.",
        "category": "Data Science",
        "price": 119.99,
    },
    {
        "title": "Object Detection with YOLO v8",
        "description": "Train and deploy custom YOLO v8 models for real-time object detection. Covers dataset preparation, augmentation, edge deployment, and API serving.",
        "category": "Computer Vision",
        "price": 79.99,
    },
    {
        "title": "Graph Neural Networks (GNNs) for Beginners",
        "description": "Understand graph-based learning and implement GCN, GAT, and GraphSAGE with PyTorch Geometric for node classification, link prediction, and graph generation.",
        "category": "Deep Learning",
        "price": 99.99,
    },
    {
        "title": "AI Safety and Responsible AI Practices",
        "description": "Explore AI alignment, model interpretability, fairness auditing, and red-teaming. Learn how to build and evaluate AI systems that are safe, unbiased, and transparent.",
        "category": "Machine Learning",
        "price": 64.99,
    },
    {
        "title": "FastAPI for Machine Learning Engineers",
        "description": "Build production-ready ML inference APIs with FastAPI, Pydantic, async background tasks, and containerization. Includes model serving patterns and load testing.",
        "category": "MLOps",
        "price": 69.99,
    },
    {
        "title": "Multi-Modal AI — Vision + Language Models",
        "description": "Learn to work with models like CLIP, Flamingo, and GPT-4V for tasks that combine images and text — visual question answering, image captioning, and document understanding.",
        "category": "NLP",
        "price": 134.99,
    },
]

USERS = [
    {"email": "admin@smartreco.ai", "password": "admin123", "role": "admin"},
    {"email": "user@smartreco.ai",  "password": "user123",  "role": "user"},
]


def main():
    print("Initializing database…")
    init_db()
    get_vector_store()  # ensure ChromaDB is ready

    db = SessionLocal()
    try:
        # ── Seed users ───────────────────────────────────────────────────────
        for u in USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"  User already exists: {u['email']}")
            else:
                user = User(
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                )
                db.add(user)
                db.commit()
                print(f"  Created user: {u['email']} ({u['role']})")

        # ── Seed products ────────────────────────────────────────────────────
        for data in COURSES:
            existing = db.query(Product).filter(Product.title == data["title"]).first()
            if existing:
                print(f"  Product already exists: {data['title'][:50]}")
                continue

            product = Product(
                title=data["title"],
                description=data["description"],
                category=data["category"],
                price=data["price"],
                vector_id="pending",
            )
            db.add(product)
            db.commit()
            db.refresh(product)

            product.vector_id = f"product_{product.id}"
            db.commit()
            db.refresh(product)

            upsert_product(product)
            print(f"  Added [{product.category}] {product.title[:55]}")

        print("\nDone! Seeded", len(COURSES), "courses and", len(USERS), "users.")
        print("  Admin login : admin@smartreco.ai / admin123")
        print("  User  login : user@smartreco.ai  / user123")

    finally:
        db.close()


if __name__ == "__main__":
    main()
