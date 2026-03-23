# AI Website Builder

Find local businesses with no website → generate a premium HTML site for each one using Claude AI → export a leads CSV ready for outreach.

**The pitch:** Open the generated HTML in a browser, show it to the business owner, and offer to host it for $50/month. Each site takes ~30 seconds and costs under $0.01 in AI credits.

---

## What it does

1. **Searches** Google Places for businesses in your niche + city
2. **Filters** for businesses that have no website listed
3. **Fetches** their real reviews, phone, and address from Google
4. **Generates** a premium, mobile-responsive HTML website using Claude AI
5. **Exports** a CSV with business name, phone, address, and path to their generated site

---

## Prerequisites

- Python 3.10+
- A **Google Places API key** (free tier covers ~$200/month of calls)
- An **Anthropic API key** (claude-3-haiku is ~$0.001 per site)

### Get your API keys

**Google Places API**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Places API**
3. Go to **Credentials** → Create API Key
4. (Recommended) Restrict the key to Places API only

**Anthropic API**
1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an account → Go to **API Keys**
3. Click **Create Key**

---

## Setup

```bash
# 1. Clone or download this project
cd website-builder

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API keys (recommended — avoids typing them every run)
export GOOGLE_PLACES_API_KEY=your_google_key_here
export ANTHROPIC_API_KEY=your_anthropic_key_here
```

> **Windows users:** Use `set` instead of `export`:
> ```
> set GOOGLE_PLACES_API_KEY=your_google_key_here
> set ANTHROPIC_API_KEY=your_anthropic_key_here
> ```

---

## Usage

```bash
python website_builder.py --niche plumber --city "Phoenix AZ" --leads 5
```

If you didn't set the environment variables, the script will prompt you to paste your keys.

### More examples

```bash
# Find 10 electricians in Austin with no website
python website_builder.py --niche electrician --city "Austin TX" --leads 10

# Find roofers in Miami
python website_builder.py --niche roofer --city "Miami FL" --leads 3

# Find HVAC companies in Denver
python website_builder.py --niche "HVAC company" --city "Denver CO" --leads 7

# Find landscapers in Seattle
python website_builder.py --niche landscaper --city "Seattle WA" --leads 5
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--niche` | Yes | Business type (plumber, electrician, roofer, landscaper, etc.) |
| `--city` | Yes | City and state ("Phoenix AZ", "Austin TX") |
| `--leads` | No | How many sites to generate (default: 5) |

---

## Output

After running, you'll find:

```
output/
├── phoenix_reliable_plumbing.html     ← Open in browser to preview
├── desert_flow_plumbing.html
├── valley_plumbing_pros.html
└── leads_plumber_phoenix_az_20240322_143012.csv   ← Your outreach list
```

### CSV columns

| Column | Description |
|--------|-------------|
| `business_name` | Full business name |
| `phone` | Formatted phone number |
| `address` | Full street address |
| `email` | Email if listed (rare via Places API) |
| `website_path` | Path to the generated HTML file |
| `rating` | Google rating (e.g. 4.7) |
| `review_count` | Number of Google reviews |
| `place_id` | Google Place ID for reference |

---

## The generated sites

Each site is a self-contained HTML file using **Tailwind CSS via CDN** (no build step needed). Features:

- **Hero section** — business name, tagline, star rating, phone CTA
- **Services section** — 6 service cards with AI-generated descriptions
- **About section** — 4 stat boxes + 2 paragraphs of AI copy
- **Reviews section** — real Google reviews, styled as cards
- **Contact section** — phone, address, hours, large CTA
- **Fixed navigation** — smooth scrolling, call button
- **Mobile responsive** — looks great on phones

Color scheme: dark navy + white + gold accents. Premium agency look.

---

## Cost estimate

| Item | Cost |
|------|------|
| Google Places Text Search | $0.032 per call (1 call per run) |
| Google Places Details | $0.017 per place checked |
| Claude Haiku per site | ~$0.001 |
| **5 leads total** | **~$0.25–$0.40** |
| **10 leads total** | **~$0.50–$0.80** |

---

## Troubleshooting

**"No businesses without websites found"**
Try a broader niche (e.g. `plumber` instead of `emergency plumber`) or a larger city.

**"Google Places API status: REQUEST_DENIED"**
Double-check your API key and that the Places API is enabled in your Google Cloud project.

**"ModuleNotFoundError"**
Run `pip install -r requirements.txt` again.

**Sites look broken in browser**
The template uses Tailwind CDN — you need an internet connection to render the styles correctly.

---

## Project structure

```
website-builder/
├── website_builder.py      # Main script — all the logic
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── sample_output.csv       # Example of what the CSV looks like
├── templates/
│   └── base_template.html  # Premium HTML template (plumber style)
└── output/                 # Generated sites and CSVs go here
    └── .gitkeep
```

---

## Extending it

- **Different niches:** The template is written for plumbers but the AI adapts the copy to any trade service. Works great for electricians, HVAC, roofers, landscapers, cleaners, etc.
- **Custom template:** Edit `templates/base_template.html`. The `{{PLACEHOLDERS}}` are substituted at runtime.
- **More review cards:** Increase `MAX_REVIEWS_TO_FETCH` at the top of `website_builder.py` (Google caps at 5 per place).
- **Email outreach:** Pipe the CSV into an email tool like Mailchimp or a cold email platform.
