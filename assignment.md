# Assignment: Sensor Measurements API

The goal of this assignment is to see how you apply practical data engineering skills in a real-world-ish setting. You'll build a backend for a simplified part of our product, with realistic expectations for quality, clarity, and completeness.

## Context

Modern greenhouses rely on lots of sensors to monitor both the external weather and the internal environment. These parameters—like temperature, humidity, CO₂ levels, and light—are influenced by both external weather and internal control systems (screens, windows, heating, etc).

We want to give growers insight into how the environment evolves over time, so they can assess and improve their growing strategy. This assignment focuses on the backend logic for a small part of that: ingesting and serving weather (meteo) data.

## Your Task

Implement a backend service with the following functionality:

### 1. API endpoints

- Ingest raw meteo data (see "Data" section below).
- Expose weather data to a frontend, with:
  - Current weather conditions (latest value per parameter)
  - 24h time series view (15 min resolution)
  - 24h average per parameter
  - 7-day time series view (1-day resolution)
  - 7-day average per parameter

### 2. Data handling

- Transform data into a clean, structured API response — don't just echo the ingestion format.
- Handle duplicates, missing data, malformed data, and other edge cases gracefully.
- Store data persistently (e.g. in a DB) so it's available between restarts.

### 3. Security & robustness

- Provide a way to ingest raw data in bulk.
- Add an appropriate level of test coverage.
- Structure your codebase so that it's easy to navigate and extend.
- Ensure the system runs locally with minimal effort.

## Requirements

- Use **Go 1.22+** or **Python 3.12+**  

- The code should be easy to understand and maintain. Performance is secondary.
- The system should run cleanly on any machine (including ours).
- You're encouraged to use LLM-assisted tools, but **you** own the code. Don't leave behind things you don't understand, and be ready to explain your implementation choices.
- Timebox to ~6-8 hours. You don't need to cover every edge case — just be clear about trade-offs.

## Deliverables

- Provide a `README.md` with:
  - Setup & run instructions
  - Testing instructions
  - Brief explanation of your architecture, assumptions, and trade-offs
  - An overview of next steps you would take if you had 3 months instead of 8 hours to work on this
- Send us a [`.git bundle`](https://stackoverflow.com/a/11795549) via email
- In the technical interview you will be asked to briefly present your solution to the interviewers as the basis for technical discussion

## Evaluation Criteria

We'll assess your work based on:

- Data modeling and storage (e.g. how flexible is the data model to new sensor types? How would it perform at scale?)
- API usability and design (e.g. how easy is it to consume the API? How easy is it to evolve the API in a backwards-compatible way?)
- Architectural choices (did you pick the right tools for the job? Did you solve problems on the infrastructure level where appropriate?)
- Code clarity and project structure (e.g. how easy is it to understand and navigate the codebase? How easy is it to contribute to the codebase?)
- Handling of real-world issues (e.g. invalid input, missing or duplicate data)
- Testing strategy (e.g. unit vs. integration tests, test coverage)
- Your ability to explain your choices and identify trade-offs or next steps

We adjust expectations based on experience level. A staff/senior engineer is expected to cover more ground than someone early in their career — especially now that LLMs can help you move faster.

## Data

Use the sample data available here:  
https://drive.google.com/drive/folders/1TV20EVuxcmaqro7e0HfmX2j6HtILNwXB?usp=sharing
