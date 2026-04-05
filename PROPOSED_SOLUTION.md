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

EVALUATION:
Model Evaluation Metrics:
1. Accuracy: Overall correctness of predicted disease class on held-out test data.
2. Precision, Recall, and F1-Score: Class-wise performance to ensure minority disease classes are not ignored.
3. Top-3 Hit Rate: Measures whether the true disease appears in the top-3 returned candidates.
4. Confusion Matrix Analysis: Identifies commonly confused disease pairs for targeted data/model improvement.

Clinical and Safety-Oriented Evaluation:
1. Gender-compatibility validation: Verify that gender-incompatible disease outputs are filtered.
2. Confidence calibration checks: Confirm that confidence decreases appropriately when vitals/history risk signals are present.
3. LLM review reliability: Track override frequency, consistency, and failure reasons when LLM review is enabled.
4. Guardrail effectiveness: Measure how often rule-based corrections prevent implausible mappings.

System and Deployment Evaluation:
1. API latency: Measure average and p95 response time for /api/predict under normal load.
2. Availability: Track successful prediction request ratio and service uptime.
3. Error monitoring: Record 4xx/5xx rates, especially LLM unavailability and external API failures.
4. Persistence validation: Confirm prediction history, health records, and ABHA-linked context are stored and retrievable correctly.

User Experience Evaluation:
1. Input completeness rate: Percentage of requests with valid symptom/profile data.
2. Output interpretability: User feedback on clarity of disease description and precautions.
3. Actionability: Whether top-3 predictions and caution context help users take next clinical steps.

Success Criteria:
1. Stable classification performance with strong Top-3 hit rate.
2. Reliable, low-latency API behavior in real-time usage.
3. Safer predictions through guardrails, profile checks, and review layers.
4. Improved trust through interpretable outputs and consistent user experience.

RESULTS:
Implemented System Outcomes:
1. End-to-end pipeline is operational from symptom input to final prediction response.
2. The model successfully returns ranked disease candidates (Top-3) with confidence values.
3. Output payload includes disease description and precautions, improving interpretability.
4. Prediction history and health context are persisted for authenticated users.

Model and Prediction Outcomes:
1. Random Forest-based multi-class disease screening is integrated and running with saved artifacts.
2. Weighted symptom feature mapping is consistently applied during inference.
3. The system supports both structured symptom selection and free-text symptom interpretation.
4. Confidence-aware prediction strategy is active, including fallback/guardrail logic.

Safety and Reliability Outcomes:
1. Gender-compatibility filtering reduces implausible disease outputs.
2. Vitals and past-medical-history signals are used to conservatively adjust confidence.
3. Optional LLM review layer is integrated for additional prediction sanity checks.
4. Strict/forced LLM strategy is supported for high-safety deployment scenarios.

Deployment and Usability Outcomes:
1. Web application is available through Flask backend with responsive frontend interface.
2. Core APIs for authentication, prediction, profile, records, and ABHA workflows are available.
3. Environment-based configuration enables local development and cloud deployment readiness.
4. Docker-based packaging support is available for portable deployment.

Result Summary:
The project delivers a practical disease prediction platform that combines machine learning, rule-based safety checks, and optional LLM-assisted review to produce interpretable and clinically cautious screening outputs in real time.

CONCLUSION:
This project demonstrates a complete and deployable disease prediction system that integrates data-driven machine learning with safety-focused decision layers. By combining symptom-based Random Forest classification, profile-aware validation, confidence calibration using vitals and medical history, and optional LLM-assisted review, the platform improves reliability and interpretability of screening outputs. The developed Flask-based application supports real-time prediction, secure user authentication, prediction history management, and ABHA-linked health context, making it suitable for practical healthcare-support use cases. Overall, the system provides a scalable foundation for early disease risk screening and can be further enhanced with larger datasets, clinical validation, and continuous performance monitoring in production environments.