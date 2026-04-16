# Quick Start

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure environment

Use `.env.example` as a base and set:

```env
MONGODB_URI=mongodb://localhost:27017/healthguard
MONGODB_DB=healthguard
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me
```

## 3. Start MongoDB

Make sure your MongoDB server is running locally or point `MONGODB_URI` to MongoDB Atlas.

## 4. Run the app

```bash
python app.py
```

## 5. Retrain model artifacts if needed

```bash
python train.py
```
