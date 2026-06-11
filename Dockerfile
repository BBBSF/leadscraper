FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "bbb_lead_scraper.cli", "run", "--sources", "all", "--days-back", "90", "--out-dir", "data/output"]
