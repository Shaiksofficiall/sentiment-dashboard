import os
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

def main():
    print("=" * 60)
    print("  TRAVEL REVIEW SENTIMENT ANALYSIS & THEME EXTRACTION MODEL")
    print("  Student Reg No: 24091A32F5")
    print("=" * 60)

    data_path = os.path.join("data", "tripadvisor_reviews_ml_ready.csv")
    model_dir = "model"
    os.makedirs(model_dir, exist_ok=True)

    # 1. Load Data
    print("\n[Step 1/7] Loading dataset...")
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df):,} reviews.")

    # Clean text column
    df['review'] = df['review'].fillna('').astype(str)

    # Ensure sentiment column exists
    if 'sentiment' not in df.columns:
        # map rating to sentiment if needed
        def map_rating(r):
            if r <= 2: return 'negative'
            elif r == 3: return 'neutral'
            else: return 'positive'
        df['sentiment'] = df['rating'].apply(map_rating)

    print("Sentiment Distribution:")
    print(df['sentiment'].value_counts())

    X = df['review']
    y = df['sentiment']

    # 2. Train/Test Split (80/20 Stratified)
    print("\n[Step 2/7] Splitting data (80/20 Stratified Train/Test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train samples: {len(X_train):,}, Test samples: {len(X_test):,}")

    # 3. TF-IDF Vectorization
    print("\n[Step 3/7] Fitting TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=10000,
        stop_words='english',
        sublinear_tf=True
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    print(f"Vocabulary size: {len(vectorizer.get_feature_names_out()):,} features.")

    # 4. Train Logistic Regression Model
    print("\n[Step 4/7] Training Logistic Regression (class_weight='balanced')...")
    classifier = LogisticRegression(
        class_weight='balanced',
        max_iter=1000,
        random_state=42,
        C=1.0
    )
    classifier.fit(X_train_vec, y_train)

    # 5. Evaluate Model Performance
    print("\n[Step 5/7] Evaluating model on test set...")
    y_pred = classifier.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nOverall Accuracy: {acc * 100:.2f}%\n")

    report_dict = classification_report(y_test, y_pred, output_dict=True)
    report_text = classification_report(y_test, y_pred)
    print("Classification Report:")
    print(report_text)

    classes = sorted(list(set(y)))
    cm = confusion_matrix(y_test, y_pred, labels=classes)
    print("Confusion Matrix (Classes: %s):" % classes)
    print(cm)

    # Top indicative words per sentiment class
    feature_names = np.array(vectorizer.get_feature_names_out())
    top_words_per_class = {}
    for i, class_label in enumerate(classifier.classes_):
        top_indices = np.argsort(classifier.coef_[i])[-15:]
        top_words_per_class[class_label] = [
            {"word": feature_names[idx], "weight": round(float(classifier.coef_[i][idx]), 4)}
            for idx in reversed(top_indices)
        ]

    # 6. Theme Extraction Service (LDA on Negative Reviews)
    print("\n[Step 6/7] Extracting themes using LDA on negative reviews...")
    neg_reviews = df[df['sentiment'] == 'negative']['review']
    
    lda_vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2)
    )
    neg_vec = lda_vectorizer.fit_transform(neg_reviews)

    lda_model = LatentDirichletAllocation(
        n_components=5,
        random_state=42,
        max_iter=15
    )
    lda_model.fit(neg_vec)

    lda_feature_names = lda_vectorizer.get_feature_names_out()
    topics = []
    topic_titles = [
        "Room Cleanliness & Maintenance",
        "Staff & Service Complaints",
        "Billing, Rates & Valet Parking",
        "Noise & Sleep Disturbance",
        "Check-in & Reservation Hassles"
    ]

    for topic_idx, topic in enumerate(lda_model.components_):
        top_features_ind = topic.argsort()[:-10:-1]
        keywords = [lda_feature_names[i] for i in top_features_ind]
        
        # Find sample reviews matching topic
        topic_scores = lda_model.transform(neg_vec)[:, topic_idx]
        top_review_indices = topic_scores.argsort()[-3:][::-1]
        sample_snippets = [neg_reviews.iloc[idx][:180] + "..." for idx in top_review_indices]

        topics.append({
            "id": topic_idx + 1,
            "title": topic_titles[topic_idx] if topic_idx < len(topic_titles) else f"Theme {topic_idx + 1}",
            "keywords": keywords,
            "sample_snippets": sample_snippets,
            "count": int(np.sum(topic_scores > 0.15))
        })
        print(f"  Theme {topic_idx + 1}: {topics[-1]['title']} -> {', '.join(keywords[:5])}")

    # 7. Save Artifacts
    print("\n[Step 7/7] Saving model artifacts to model/...")
    joblib.dump(classifier, os.path.join(model_dir, "model.pkl"))
    joblib.dump(vectorizer, os.path.join(model_dir, "vectorizer.pkl"))
    joblib.dump(lda_model, os.path.join(model_dir, "lda.pkl"))
    joblib.dump(topics, os.path.join(model_dir, "lda_topics.pkl"))

    # Compute overall dashboard metrics
    dashboard_stats = {
        "reg_no": "24091A32F5",
        "total_reviews": len(df),
        "avg_rating": round(float(df['rating'].mean()), 2),
        "accuracy": round(float(acc) * 100, 2),
        "sentiment_counts": df['sentiment'].value_counts().to_dict(),
        "rating_counts": df['rating'].value_counts().to_dict(),
        "confusion_matrix": cm.tolist(),
        "classes": classes,
        "classification_report": report_dict,
        "top_words_per_class": top_words_per_class
    }
    joblib.dump(dashboard_stats, os.path.join(model_dir, "dashboard_stats.pkl"))

    print("\nModel training and artifact generation completed successfully!")
    print(f"Artifacts saved in ./{model_dir}/:")
    for f in os.listdir(model_dir):
        print(f"  - {f}")

if __name__ == "__main__":
    main()
