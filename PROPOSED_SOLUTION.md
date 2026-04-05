PROBLEM STATEMENT:
Early identification of likely diseases from symptom patterns is difficult for many users due to scattered health information, non-standard symptom descriptions, and limited access to immediate screening support. Existing manual approaches can be slow, inconsistent, and prone to error, especially when symptom combinations overlap across multiple conditions. This project addresses the problem by building a secure, real-time disease prediction system that accepts structured and free-text symptoms, applies a trained machine learning model for multi-class disease screening, and returns interpretable outputs including confidence score, top alternatives, description, and precautions. The system further improves reliability through profile-aware checks, vitals/history-based confidence adjustment, and optional LLM-assisted safety review, while maintaining user authentication, prediction history, and ABHA-linked health context in a practical web application.

PROPOSED SOLUTION:
The system is designed as an end-to-end healthcare prediction pipeline that collects user symptoms, processes structured and unstructured inputs, predicts likely diseases, and returns explanation, precautions, and confidence with optional LLM safety review.

Data Collection:
Objective: Gather reliable symptom and profile inputs for disease risk screening.
Sources: Curated disease-symptom datasets in local CSV files, user-entered symptoms, user profile data, optional health vitals, and ABHA-linked historical records.
Key Parameters: Symptom set, symptom severity weights, patient gender, optional vitals (temperature, heart rate, blood pressure, oxygen saturation, blood sugar), and past illness history.
Engineering Approach: Flask API endpoints collect data from frontend forms and free-text symptom input, normalize the payload, and map it into the trained model feature space.

Data Preprocessing:
Before feeding data into the model:
Apply the same preprocessing steps used during training:
Symptom normalization (strip/clean/lowercase)
Weighted symptom vector construction using Symptom-severity mapping
Feature alignment with persisted symptom_list order from training artifacts
No scaling is required (Random Forest is scale-independent)
Rule-based compatibility checks (for example, gender-incompatible disease filtering)
Confidence adjustment layer using vitals context and medical history recurrence signals.

Machine Learning Algorithm:
Random Forest Classifier is used as the primary disease prediction model.
Each tree is trained on a random subset of data and features.
Final disease probabilities are computed by aggregating outputs across all trees.
Top-3 disease candidates are generated from class probabilities.
This approach reduces overfitting and improves generalization for multi-class disease classification.

Deployment:
Develop and run a user-friendly web application that provides real-time disease prediction, top candidate ranking, confidence score, disease description, and precaution guidance.
The current project is deployed as a Flask backend with a responsive HTML/CSS/JavaScript frontend and optional Docker support.

SYSTEM APPROACH:
System requirements:
1. Windows 10/11 or Linux/macOS
2. Intel i3-class CPU or above, minimum 4 GB RAM recommended
Library required to build and run the model/application:
3. flask
4. flask-cors
5. flask-jwt-extended
6. flask-sqlalchemy
7. sqlalchemy
8. python-dotenv
9. pandas
10. numpy
11. scikit-learn
12. joblib
13. requests

ALGORITHM & DEPLOYMENT:
Algorithm Selection:
Random Forest is an ensemble learning algorithm that constructs multiple decision trees during training and combines their outputs to improve predictive accuracy and stability.
Each tree is trained on a random subset of the dataset (bagging).
At each split, a random subset of features is considered.
For prediction:
Classification -> majority decision with class-probability aggregation (disease classes).
This controlled randomness reduces overfitting and improves generalization compared to a single decision tree.

Model Training
Data Input:
The Random Forest model is trained using disease-symptom records and weighted symptom features:
Bootstrap sampling (bagging): Each tree is trained on a random subset of training rows.
Random feature selection: At each split, only a subset of symptom features is considered.
Each tree learns different symptom-pattern relationships, and their predictions are combined into robust disease probabilities.
Training output artifacts are persisted as model.pkl, symptom_list.pkl, and severity_map.pkl.

Prediction Process:
Once the Random Forest model is trained, incoming symptoms are transformed into the same weighted feature vector used during training.
The model returns top disease candidates and confidence.
A post-prediction safety layer applies guardrails, vitals/history confidence adjustments, and optional LLM review.
Final API output includes selected disease, confidence score, top-3 alternatives, explanation, and precautions for user action.