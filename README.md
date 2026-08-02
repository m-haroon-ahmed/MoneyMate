# 💰 Money Mate

A desktop personal finance tracker built with **Python (Tkinter)**. Track income and expenses, set monthly category budgets that carry forward automatically, visualize spending with charts, and filter your history by date, category, or amount.

## Features

- **Income & Expense Tracking** — add, edit, delete, and search transactions
- **Custom Categories** — pick from suggested categories or type your own on the fly
- **Per-Month Budget Limits** — set a budget for each category per month; unedited months automatically carry forward the last set value, while past months keep their own history
- **Budget Alerts** — get warned when you're near, at, or over a category's limit
- **Flexible Filtering** — All Time / This Month / This Year, a Previous/Next month browser, a custom date range, text search, and an amount range filter
- **Visual Dashboard** — live balance, income, and expense summary synced to your selected filter
- **Charts** — category-wise expense pie chart and a 6-month income vs. expense bar chart (opens in its own window)
- **Data Safety** — every save is atomic and automatically backed up; if the data file ever gets corrupted, the app recovers from the last good backup

## Tech Stack

- **Python 3**
- **Tkinter** / **ttk** — GUI
- **Matplotlib** — charts
- **JSON** — local data storage (`money_mate_data.json`)

## Getting Started

### Prerequisites
- Python 3.8 or newer installed ([python.org](https://www.python.org/downloads/))

### Installation
```bash
# 1. Clone this repository
git clone https://github.com/m-haroon-ahmed/Money-Mate.git
cd Money-Mate

# 2. Install the one required dependency (charts)
pip install matplotlib

# 3. Run the app
python Money_Mate_Complete.py
```

On first run, the app creates a `money_mate_data.json` file in the same folder to store your data.

## Screenshots

*(Add a screenshot or two here — drag an image into this README on GitHub and it will generate the markdown for you.)*

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Author

**M Haroon Ahmed**
[GitHub](https://github.com/m-haroon-ahmed)
