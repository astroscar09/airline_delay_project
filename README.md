# Airline Delay Analysis Project


# Airline Delay Analysis Project

![GitHub last commit](https://img.shields.io/github/last-commit/astroscar09/airline_delay_project)
![GitHub repo size](https://img.shields.io/github/repo-size/astroscar09/airline_delay_project)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)


This repository contains the code and infrastructure to **analyze airline flight delays in an automated and scalable way**. The goal of the project is to ingest airline data provided by the government, clean and store it in a database, and compute key metrics that can be used for visualization and further analysis.

The data is publicly available from the Bureau of Transportation Statistics: [Airline On-Time Performance Data](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ&QO_fu146_anzr=b0-gvzr).

---

## Project Goals

- Handle **real-world data** and demonstrate data engineering and analytics skills.  
- Use **Python and SQLite** to manage and query the data.  
- Automate the ingestion process so that the workflow is **scalable** with new incoming data.  
- Recompute tables and metrics **on-the-fly**, producing outputs ready for visualization in tools like **Tableau**, **Power BI**, or Python plotting libraries.  

---

## Features

- Automated ingestion pipeline for CSV data.  
- SQLite database integration to store raw and processed data.  
- Computation of key metrics, such as monthly delays, airline comparisons, and rolling statistics.  
- Outputs ready for visualization and reporting.  

---

## Usage

1. Clone the repository:

```bash
git clone https://github.com/astroscar09/airline_delay_project.git
cd airline_delay_project
