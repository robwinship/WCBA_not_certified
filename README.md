# WCBA Outstanding Coach Certifications

A GitHub Pages site that tracks and displays coaches with outstanding certification requirements in the Western Coaching Baseball Association local associations.

## Overview

This site provides a summary view of coaches who have not yet completed their coaching certifications for the 2026 season. Data is organized by local association and automatically updated daily.

### Tracked Local Associations
- Alvinston
- Blenheim
- Chatham
- Corunna
- Dresden
- Dutton
- Lambton Shores
- Port Lambton
- Sarnia
- Wallaceburg
- Wyoming

## How It Works

### 1. **Web Scraper** (`scraper.py`)
- Runs automatically every day at 8:00 AM Eastern Time
- Fetches the latest data from the [OBA Coach Certification page](https://www.registeroba.ca/certification-inprogress-by-local)
- Uses Playwright plus Wix cloud-data responses for JavaScript-rendered content
- Falls back between cloud-data and rendered HTML for better coverage
- Filters data to include only the local associations listed above
- Always includes all tracked locals in `data.json` (locals with no current rows remain at 0)

### 2. **GitHub Actions** (`.github/workflows/scrape-daily.yml`)
- Scheduled to run the scraper daily
- Automatically commits and pushes data changes
- Can be manually triggered

### 3. **GitHub Pages** (`index.html`)
- Simple, responsive HTML/CSS site
- Displays coaches grouped by local association
- Interactive cards showing/hiding coach details
- Real-time data loaded from `data.json`

## Local Development

### Prerequisites
- Python 3.7+
- `requests` library: `pip install requests`
- `beautifulsoup4` library: `pip install beautifulsoup4`
- `playwright` library: `pip install playwright`
- Playwright browser install: `python -m playwright install chromium`

### Running the Scraper Locally
```bash
python scraper.py
```

This will:
1. Fetch the latest data from the OBA website
2. Filter for the target local associations
3. Generate an updated `data.json` file

### Testing the Site Locally
Simply open `index.html` in a web browser. The site will load `data.json` and display the coaches.

## Data Structure

The `data.json` file contains:

```json
{
  "last_updated": "ISO-8601 timestamp",
  "updates_at": "8:00 AM Eastern",
  "locals": {
    "Local Name": {
      "count": 10,
      "coaches": [
        {
          "name": "Coach Name",
          "position": "12U AA Assistant Coach",
          "reg_id": "1234567"
        },
        ...
      ]
    },
    ...
  }
}
```

## Features

- 📊 **Summary Statistics**: Total number of local associations and coaches
- 🎨 **Clean UI**: Responsive design works on desktop and mobile
- 📱 **Interactive Cards**: Click to expand/collapse coach details for each local
- ⏰ **Auto Updates**: Data refreshes daily at 8:00 AM Eastern
- 🔗 **Source Attribution**: List links back to the original OBA data

## GitHub Pages Setup

The site is configured to use GitHub Pages with the repository root as the source.

**To enable/verify GitHub Pages:**
1. Go to repository Settings → Pages
2. Ensure "Source" is set to "Deploy from a branch"
3. Select the `main` (or `master`) branch
4. Select `/ (root)` as the folder
5. Click Save

Your site will be available at: `https://robwinship.github.io/WCBA_Coaches_Outstanding`

## Customization

### Adding/Removing Local Associations
Edit the `TARGET_LOCALS` set in `scraper.py`:

```python
TARGET_LOCALS = {
    'alvinston',
    'blenheim',
    # ... add or remove as needed
}
```

### Changing Update Schedule
Edit the cron schedule in `.github/workflows/scrape-daily.yml`:

```yaml
- cron: '0 12 * * *'  # Change this line
```

Cron format: `minute hour day month day-of-week`
- `0 12 * * *` = Daily at 12:00 UTC (8 AM EST / 9 AM EDT)

### Styling
All CSS is embedded in `index.html`. Modify the `<style>` section to customize colors and layout.

## Troubleshooting

### Data Not Updating
1. Check GitHub Actions: Go to "Actions" tab in the repository
2. Find the "Daily OBA Coach Scraper" workflow
3. Review logs for errors
4. Manually trigger: Click "Run workflow" → "Run workflow" button

### Website Shows Old Data
1. Hard refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Check the "Last updated" timestamp at the bottom
3. Verify `data.json` has recent updates on GitHub

### Scraper Not Finding Coaches
The website structure may have changed:
1. Run the scraper locally to debug
2. Verify Playwright browser install (`python -m playwright install chromium`)
3. Verify the OBA URL structure hasn't changed
4. Check logs for cloud-data/API or HTML fallback parsing messages

## Git Configuration

The GitHub Actions workflow uses this configuration for commits:
- **Username**: robwinship
- **Email**: robwinship@hotmail.com

These are configured in `.github/workflows/scrape-daily.yml` and can be updated as needed.

## License

This project is for informational purposes and displays publicly available data from the Ontario Baseball Association.

## Support

For issues or improvements, please open an issue in the GitHub repository.

---

**Data Source**: [Ontario Baseball Association - Coach Certification Status](https://www.registeroba.ca/certification-inprogress-by-local)

**Last Updated**: See the timestamp at the bottom of the website
