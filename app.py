from shiny import App, reactive, render, ui
import pandas as pd
import random
from pathlib import Path
from starlette.staticfiles import StaticFiles
import csv
import os
from datetime import datetime

# Helper function to sanitize section names for button IDs
def sanitize_id(name):
    return ''.join(c if c.isalnum() else '_' for c in name)

# Helper function to normalize units for comparison
def normalize_units(unit_str):
    """Convert between old CSV format and new Unicode format"""
    if pd.isna(unit_str):
        return unit_str
    unit_str = str(unit_str).strip()
    # Convert old format to new format
    unit_str = unit_str.replace('^2', '²')
    unit_str = unit_str.replace('.', '·')
    return unit_str

# Get the current directory and construct path to CSV
current_dir = Path(__file__).parent
csv_path = current_dir / "Master_questions.csv"

# Cache-busting timestamp for static assets
import time
cache_buster = reactive.Value(int(time.time()))

# Function to load CSV data
def load_csv_data():
    import io
    # Try multiple encodings to handle different file formats
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'windows-1252', 'iso-8859-1']
    content = None
    
    for encoding in encodings:
        try:
            with open(csv_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
                # Replace Windows line endings with Unix ones
                content = content.replace('\r\n', '\n').replace('\r', '\n')
            break  # Successfully read the file
        except (UnicodeDecodeError, Exception) as e:
            if encoding == encodings[-1]:  # Last encoding attempt
                # If all encodings fail, try with error handling
                with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    content = content.replace('\r\n', '\n').replace('\r', '\n')
            continue
    
    # Now parse the cleaned content
    df = pd.read_csv(io.StringIO(content))
    df["correct_option"] = (
        pd.to_numeric(df["correct_option"], errors="coerce")
          .astype("Int64")   # capital "I" — pandas' nullable integer
    )
    return df

# Load and process the data initially
df = reactive.Value(load_csv_data())

# drop any nan section values - load data directly for initial sections list
initial_df = load_csv_data()
sections = (
    initial_df["section"]
      .dropna()        # remove NaN
      .astype(str)     # ensure every entry is a string
      .unique()
      .tolist()
)

# Define color palette for section buttons (background_color, text_color)
SECTION_COLORS = [
    ("#4a85d6", "white"),   # Brighter blue
    ("#8560b8", "white"),   # Brighter purple
    ("#50a876", "white"),   # Brighter green
    ("#d15d5d", "white"),   # Brighter red
    ("#e68f42", "white"),   # Brighter orange
    ("#4db399", "white"),   # Brighter teal
    ("#4a98b8", "white"),   # Brighter cyan
    ("#d66b99", "white"),   # Brighter pink
    ("#7360a3", "white"),   # Brighter indigo
    ("#e6b84a", "#333"),    # Brighter yellow (with dark text)
    ("#5d7599", "white"),   # Brighter gray
    ("#b36d4d", "white"),   # Brighter brown
    ("#5d7f99", "white"),   # Brighter blue-gray
    ("#ad5dad", "white"),   # Brighter deep purple
    ("#5db3d1", "white"),   # Brighter light cyan
    ("#e66b4a", "white"),   # Brighter deep orange
    ("#85ba5d", "#333"),    # Brighter light green (with dark text)
    ("#ccb84a", "#333"),    # Brighter lime (with dark text)
    ("#e6a335", "white"),   # Brighter amber
    ("#50a380", "white"),   # Brighter teal variant
]

def get_section_color(section_name, section_list):
    """Get color for a section based on its index in the section list"""
    try:
        idx = section_list.index(section_name)
        return SECTION_COLORS[idx % len(SECTION_COLORS)]
    except (ValueError, IndexError):
        return ("#6c757d", "white")  # Default gray

# Store the ID of the last shown notification (so we can remove it if a new one appears)
last_notification_id = reactive.Value(None)

# Track whether app is on its initial load
initial_load = reactive.Value(True)

# **Reactive Value to Track Section Selection**
is_section_selected = reactive.Value(False)
show_analytics = reactive.Value(False)
# **Landing Page UI Component**
landing_page_ui = ui.page_fluid(
    ui.div(
        ui.h1("Welcome to the Biomechanics Tutor", class_="welcome-title"),
        ui.p("Please select a section to begin:", class_="welcome-subtitle"),
        ui.p("Build refreshed: 2026-07-26 (Mantine + icons)", class_="welcome-subtitle"),
        # **Dynamic Section Buttons**
        ui.div(
            [
                ui.input_action_button(
                    f"section_button_{sanitize_id(section)}",
                    ui.HTML(f'<iconify-icon icon="tabler:notebook"></iconify-icon><span>{section}</span>'),
                    class_="section-button",
                    style=f"background-color: {get_section_color(section, sections)[0]}; color: {get_section_color(section, sections)[1]};"
                )
                for section in sections 
            ],
            class_="section-buttons-container",
        ),
        class_="landing-container",
    )
)

# **Combined UI with Conditional Rendering**
app_ui = ui.page_fluid(
    ui.output_ui("main_ui"),
    ui.tags.head(
        # Include KaTeX and Marked.js for client-side rendering
        ui.tags.link(
            rel="stylesheet",
            href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css",
        ),
        ui.tags.script(
            src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"
        ),
        ui.tags.script(
            src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
        ),
        ui.tags.script(
            src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"
        ),
        ui.tags.script(
            src="https://code.iconify.design/iconify-icon/2.1.0/iconify-icon.min.js"
        ),

        ui.tags.script(
            # Minimal functional change: second pass ensures markdown-only (no KaTeX) renders
            r"""
            // --- Instant markdown + KaTeX rendering (no round-trip, no artificial delay) ---
            function _renderMathIn(elem) {
                if (typeof renderMathInElement === 'undefined') return;
                try {
                    renderMathInElement(elem, {
                        delimiters: [
                            {left: "$$", right: "$$", display: true},
                            {left: "$", right: "$", display: false}
                        ],
                        throwOnError: false
                    });
                } catch (mathError) {
                    console.error("Error in renderMathInElement:", mathError);
                }
            }

            // Reveal a pre-render card, but wait for ITS OWN images to finish
            // loading first so text + image appear together (no layout-shift flicker).
            // Image-less cards reveal instantly. A safety timeout guarantees the card
            // never stays hidden if an image is slow or broken.
            function revealCard(card) {
                if (!card || !card.classList) return;
                if (card.classList.contains('ready')) return;
                var imgs = card.querySelectorAll ? card.querySelectorAll('img') : [];
                var pending = [];
                for (var i = 0; i < imgs.length; i++) {
                    var img = imgs[i];
                    if (!img.complete || img.naturalHeight === 0) {
                        pending.push(img);
                    }
                }
                if (pending.length === 0) {
                    card.classList.add('ready');
                    return;
                }
                if (card._revealScheduled) return;
                card._revealScheduled = true;
                var remaining = pending.length;
                var done = false;
                function finish() {
                    if (done) return;
                    done = true;
                    card.classList.add('ready');
                }
                function one() {
                    remaining -= 1;
                    if (remaining <= 0) finish();
                }
                for (var k = 0; k < pending.length; k++) {
                    pending[k].addEventListener('load', one, {once: true});
                    pending[k].addEventListener('error', one, {once: true});
                }
                // Safety: never hide the card longer than 1.5s waiting on images
                setTimeout(finish, 1500);
            }

            // Render a single element the moment it exists in the DOM
            function renderOne(elem) {
                try {
                    if (!elem) return;
                    if (elem.getAttribute && elem.getAttribute('data-rendered') === '1') return;
                    var markdownText = elem.getAttribute ? elem.getAttribute('data-markdown') : null;
                    if (markdownText !== null && typeof markdownText !== 'undefined') {
                        if (typeof marked === 'undefined') return; // parser not ready yet; retry later
                        var processedText = markdownText;
                        if (elem.classList && elem.classList.contains('correct-answer-highlight')) {
                            // single-line flow for the highlighted correct answer
                            processedText = processedText.replace(/\$\$/g, '$');
                        }
                        elem.innerHTML = marked.parse(processedText);
                        elem.setAttribute('data-rendered', '1');
                    }
                    _renderMathIn(elem);
                    elem.style.visibility = "visible";
                    // Reveal the containing pre-render card immediately
                    var card = elem.closest ? elem.closest('.card-prerender') : null;
                    if (card) revealCard(card);
                } catch (error) {
                    console.error("Error in renderOne:", error);
                }
            }

            // Public helpers kept for backwards-compatible custom messages (now instant)
            function renderContent(selector) {
                document.querySelectorAll(selector).forEach(function(elem) {
                    elem.removeAttribute('data-rendered');
                    renderOne(elem);
                });
            }

            function fullyRenderCard(cardSelector, contentSelector) {
                var card = document.querySelector(cardSelector);
                if (!card) return;
                card.querySelectorAll(contentSelector).forEach(function(elem) {
                    elem.removeAttribute('data-rendered');
                    renderOne(elem);
                });
                revealCard(card);
            }

            // Watch the DOM and render new content the instant Shiny inserts it.
            // This removes dependence on the Python->JS message round-trip and all timers,
            // so switching question / step renders seamlessly with no blank flash.
            var _mdObserver = new MutationObserver(function(mutations) {
                for (var mi = 0; mi < mutations.length; mi++) {
                    var nodes = mutations[mi].addedNodes;
                    for (var ni = 0; ni < nodes.length; ni++) {
                        var node = nodes[ni];
                        if (!node || node.nodeType !== 1) continue;
                        if (node.hasAttribute && node.hasAttribute('data-markdown')) {
                            renderOne(node);
                        }
                        if (node.querySelectorAll) {
                            node.querySelectorAll('[data-markdown]').forEach(renderOne);
                            if (node.classList && node.classList.contains('card-prerender')) {
                                revealCard(node);
                            }
                            node.querySelectorAll('.card-prerender').forEach(function(c) {
                                revealCard(c);
                            });
                        }
                    }
                }
            });

            function _startMdObserver() {
                if (document.body) {
                    _mdObserver.observe(document.body, {childList: true, subtree: true});
                    // Render anything already present
                    document.querySelectorAll('[data-markdown]').forEach(renderOne);
                    document.querySelectorAll('.card-prerender').forEach(function(c){ revealCard(c); });
                } else {
                    setTimeout(_startMdObserver, 20);
                }
            }
            _startMdObserver();

            // Safety net: once the CDN parsers finish loading, render any nodes
            // that were inserted before marked/KaTeX were available.
            window.addEventListener('load', function() {
                document.querySelectorAll('[data-markdown]').forEach(function(elem) {
                    if (elem.getAttribute('data-rendered') !== '1') renderOne(elem);
                });
            });

            Shiny.addCustomMessageHandler('render-math', function(message) {
                renderContent(message.selector);
            });

            Shiny.addCustomMessageHandler('render-card', function(message) {
                fullyRenderCard(message.cardSelector, message.contentSelector);
            });
            """
        ),
        # Script to collapse the nav on custom message (hamburger toggler)
        ui.tags.script(
            """
            function toggleMobileMenu() {
                var buttons = document.getElementById('headerButtons');
                if (buttons) {
                    buttons.classList.toggle('show');
                }
            }
            
            // Close mobile menu when clicking outside
            document.addEventListener('click', function(event) {
                var buttons = document.getElementById('headerButtons');
                var hamburger = document.querySelector('.hamburger-menu');
                if (buttons && hamburger && 
                    !buttons.contains(event.target) && 
                    !hamburger.contains(event.target)) {
                    buttons.classList.remove('show');
                }
            });
            
            // Close mobile menu when a button is clicked
            document.addEventListener('click', function(event) {
                if (event.target.classList.contains('header-main-menu-btn')) {
                    var buttons = document.getElementById('headerButtons');
                    if (buttons) {
                        buttons.classList.remove('show');
                    }
                }
            });
            """
        ),
        # Script for localStorage
        ui.tags.script(
            """
            Shiny.addCustomMessageHandler('save_csv', function(message) {
                localStorage.setItem('biomechanics_data', message.csv);
            });
            $(document).on('shiny:connected', function() {
                var csv = localStorage.getItem('biomechanics_data');
                Shiny.setInputValue('loaded_csv', csv || '');
            });
            """
        ),
        ui.tags.style(
        """
        /* ---------------- GLOBAL LAYOUT / BODY ----------------
           Controls overall page background and margin */
        body {
            background-color: #e0e0e0 !important; /* Gray background */
            margin: 0 !important;                /* Remove default page margin */
        }

        /* ---------------- NAVBAR ----------------
           (Kept in case other navbars exist; no longer used for header) */
        .navbar {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            z-index: 9999 !important;
        }

        /* ---------------- NOTIFICATIONS ----------------
           Appear ~50px from top, aligned to right */
        .shiny-notification {
            position: fixed !important;
            top: 50px !important;
            right: 10px !important;
            bottom: auto !important;
        }

        /* ---------------- TITLE CONTAINER ----------------
           For the main page title. */
        .title-container {
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            background-color: #f8f9fa !important; /* Light gray background */
        }

        /* ---------------- #combined_answer ----------------
           Displays the numeric+units text. Slightly bigger font, 
           aligned vertically */
        #combined_answer {
            color: #6c757d;
            font-weight: 500;
            font-size: 1.1em;
            padding: 6px 0 !important;
            margin: 0 !important;
            border-top: none !important;
            display: flex !important;
            align-items: center !important;
            height: 38px !important;
        }

        /* ---------------- SELECTIZE / FORM CONTROLS ----------------
           Minimizes extra space on selectize controls and form fields */
        .selectize-control {
            min-width: 100px !important;
            max-width: 100% !important;
            margin: 0px !important;
            padding: 6px !important;
            height: 38px !important;
        }
        .selectize-dropdown, .selectize-input, .selectize-input input {
            padding: 0px !important;
            margin: 0px !important;
        }
        .form-control {
            max-width: 100% !important;
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            padding: 0px !important;
            height: 38px !important;
        }
        .form-control, .selectize-control {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            padding: 0px !important;
        }

        /* 
           .col-4, .col-8, .col-12 
           Adjust column spacing to be minimal 
        */
        .col-8, .col-4, .col-12 {
            padding: 4px !important;
            margin: 0 !important;
        }

        /* ---------------- QUESTION BANNER ----------------
           The banner at the top of each question card */
        .question-banner {
            background-color: #ffffff;
            border-radius: 8px 8px 0 0;
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            padding: -10px 0px !important;
            border-bottom: 0px solid #ffffff;
        }
        .question-banner2 {
            background-color: #ffffff;
            border-radius: 8px 8px 0 0;
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            padding: -10px 0px !important;
            border-bottom: 0px solid #ffffff;
        }

        /* ---------------- CARD CONTENT ----------------
           .card > div => add consistent left/right padding inside the card */
        .card > div {
            padding-left: 20px !important;
            padding-right: 20px !important;
        }

        /* ---------------- QUESTION TITLE ----------------
           The heading text inside .question-banner */
        .question-title {
            color: #333;
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-weight: 600;
            font-size: 20px;
            letter-spacing: 0.5px;
            text-transform: none;
            margin-top: -15px !important;
            margin-bottom: -20px !important;
            padding: 6px 0;
        }
        .question-title2 {
            color: #333;
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-weight: 600;
            font-size: 20px;
            letter-spacing: 0.5px;
            text-transform: none;
            margin-top: -5px !important;
            margin-bottom: -20px !important;
            padding: 6px 0;
        }

        /* ---------------- MAIN PAGE TITLE (TUTOR-TITLE) ----------------
           The top-level title in the shared header */
        .tutor-title {
            color: #333;
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-weight: 600;
            font-size: 28px;
            letter-spacing: 0.5px;
            text-transform: none;
            margin: 0;
            padding: 0;
        }

        /* ---------------- SHARED HEADER (TITLE + MAIN MENU LINK) ---------------- */
        .tutor-header {
            background-color: #f8f9fa;
            padding: 10px 16px;
            border-bottom: 1px solid #ddd;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            width: 100%;
            margin: 0;
            z-index: 100;
        }
        
        /* Hamburger menu styles */
        .hamburger-menu {
            display: none;
            flex-direction: column;
            cursor: pointer;
            padding: 5px;
            z-index: 1001;
        }
        
        .hamburger-menu span {
            width: 25px;
            height: 3px;
            background-color: #333;
            margin: 3px 0;
            transition: 0.3s;
        }
        
        .header-buttons {
            display: flex;
            gap: 10px;
        }
        
        /* Mobile styles */
        @media (max-width: 767px) {
            .hamburger-menu {
                display: flex;
            }
            
            .header-buttons {
                display: none;
                position: fixed;
                top: 60px;
                right: 0;
                background-color: #f8f9fa;
                flex-direction: column;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                z-index: 1000;
                gap: 5px;
            }
            
            .header-buttons.show {
                display: flex;
            }
            
            .tutor-title {
                font-size: 20px !important;
            }
        }
        
        @media (min-width: 768px) {
            .tutor-header {
                margin-bottom: 5px;
            }
        }
        .tutor-footer {
            background-color: #f8f9fa;
            padding: 10px 16px;
            border-top: 1px solid #ddd;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            width: 100%;
            z-index: 1000;
            gap: 10px;
        }
        
        /* Ensure body wrapper doesn't expand */
        .page-fluid {
            display: block !important;
            height: auto !important;
            min-height: 0 !important;
            max-height: none !important;
        }
        
        /* Target main wrapper - keep minimal constraints */
        #main-wrapper {
            height: auto;
            min-height: 0;
            overflow: visible;
        }
        
        /* Analytics wrapper - use class for higher specificity */
        .analytics-wrapper {
            position: fixed;
            top: 80px;
            left: 0;
            right: 0;
            bottom: 60px;
            overflow-y: auto;
            overflow-x: hidden;
            z-index: 1;
            background: #f8f9fa;
        }
        
        /* Ensure shiny output inside wrapper doesn't create extra height */
        .analytics-wrapper > * {
            height: 100%;
            overflow: visible;
        }
        
        /* Remove any potential padding/margin from containers */
        #main-wrapper::after, #main-wrapper::before,
        .page-fluid::after, .page-fluid::before {
            display: none !important;
            content: none !important;
        }
        
        /* Add padding for fixed header and footer */
        body, .bslib-page-fluid, .page-fluid {
            padding-top: 65px !important;
            padding-bottom: 60px !important;
        }
        
        #main-wrapper {
            padding-bottom: 0px !important;
        }
        
        /* Ensure all parent containers collapse properly */
        body, html, .bslib-page-fluid {
            overflow-y: auto !important;
            overflow-x: hidden !important;
        }
        
        /* Prevent KaTeX from expanding page height ONLY in analytics sections */
        .analytics-answer-cell .katex-display,
        .analytics-step-detail .katex-display {
            display: inline !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        .header-main-menu-btn, .footer-btn {
            font-weight: 500;
            text-transform: none;
            border-radius: 12px;
            text-decoration: none !important;
            white-space: nowrap;
            padding: 6px 14px;
            background-color: transparent;
            border: 1px solid transparent;
            color: #007bff;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .header-main-menu-btn:hover, .footer-btn:hover {
            background-color: #e9ecef;
            color: #0056b3;
        }

        /* ---------------- PRIMARY BUTTONS ----------------
           e.g. "Submit Answer" */
        .btn-primary {
            background-color: #4a85d6;
            border: 1px solid #4a85d6;
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 6px;
            transition: all 0.3s ease;
            width: auto;
            margin: 0 !important;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: none;
            cursor: pointer;
            height: 38px;
        }
        .btn-primary:hover {
            border-color: #3570c2;
            color: #3570c2;
            background-color: #ffffff;
        }
        .btn-primary:active {
            background-color: #ffffff;
            border-color: #4a85d6;
            color: #4a85d6;
        }

        /* ---------------- OPTION BUTTON ----------------
           For multiple-choice cards */
        .option-button {
            transition: all 0.3s ease;
            border: 1px solid #6c757d !important;
            background-color: #ffffff !important;
            padding: 15px !important;
            margin: 0 !important;
            border-radius: 8px !important;
            width: 100% !important;
            height: auto !important;
            min-height: 120px !important;
            max-height: none !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            color: #333 !important;
            cursor: pointer;
        }
        .option-button:hover {
            border-color: #4a85d6 !important;
            color: #4a85d6 !important;
            background-color: #ffffff !important;
        }
        
        /* Ensure ALL button wrappers can grow with content */
        .option-button,
        .option-button > *,
        .option-button > * > * {
            max-width: 100% !important;
        }
        
        /* Force all button wrapper divs to auto height */
        .bslib-gap-spacing > div,
        [class*="html-fill-container"] {
            height: auto !important;
        }

        /* 
           Inline images inside .card 
           -> margin top/bottom, side padding
        */
        .card img {
            margin: 10px 0 25px 0;
            padding: 0 20px;
            max-width: 100% !important;
        }
        
        /* Limit images in correct answer highlights to 300px height */
        .correct-answer-highlight img {
            height: auto !important;
            width: auto !important;
            max-width: 100% !important;
            max-height: 300px !important;
            display: block !important;
        }
        
        /* Limit images in option buttons to 300px height */
        .option-button img {
            height: auto !important;
            width: auto !important;
            max-width: 100% !important;
            max-height: 300px !important;
            display: block !important;
        }

        /* ---------------- QUESTION STEPS (NAV-PILLS) ---------------- 
           For steps inside main_content => .nav-pills, etc. */
        .question_steps {
            padding: 0 !important;
            margin: 0 !important;
        }
        .question_steps .nav-pills {
            margin-top: 0 !important;
            margin-bottom: 10px !important;
            padding-left: 0px !important;
            background: none !important;
            row-gap: 10px;
        }
        .question_steps .nav-pills .nav-link {
            color: #ffffff;
            background-color: #4a85d6;
            border: 1px solid #4a85d6;
            margin-right: 8px;
            border-radius: 6px;
            padding: 10px 25px;
            transition: all 0.2s ease;
            font-weight: 500;
            min-width: 100px;
            text-align: center;
            /* equal width & fixed height */
            width: 120px !important;
            flex: 0 0 120px !important;
            height: 45px !important;
        }
        .question_steps .nav-pills .nav-link:hover {
            border-color: #3570c2;
            color: #3570c2;
            background-color: #ffffff;
        }
        .question_steps .nav-pills .nav-link.active {
            border-color: #4a85d6;
            color: #4a85d6;
            background-color: #ffffff;
        }
        .question_tabs {
            margin-bottom: 10px;
        }

        /* ---------------- NAV-TABS (QUESTION NAV) ----------------
           For .question_nav => .nav-tabs */
        .nav-tabs {
            margin-top: 10px;
            margin-bottom: 10px;
            background: none !important;
            border-bottom: none !important;
            row-gap: 10px;
            padding-left: 0px !important;
        }
        .nav-tabs .nav-link {
            color: #ffffff;
            background-color: #4a85d6;
            border: 1px solid #4a85d6;
            margin-right: 4px;
            border-radius: 6px;
            padding: 8px 20px;
            transition: all 0.2s ease;
            font-weight: 500;
            /* equal width & fixed height */
            width: 60px !important;
            flex: 0 0 60px !important;
            height: 45px !important;
            text-align: center !important;
        }
        .nav-tabs .nav-link:hover {
            border-color: #3570c2;
            color: #3570c2;
            background-color: #ffffff;
        }
        .nav-tabs .nav-link.active {
            border-color: #4a85d6;
            color: #4a85d6;
            background-color: #ffffff;
        }

        /* ---------------- CARD STYLING ----------------
           Used for question_card, main_content, etc. */
        .card {
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            position: relative !important;
            padding: 0 !important;
        }
        .card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .card .row {
            margin-top: 0px;
            margin-bottom: 0px;
            padding: 0;
        }
        
        /* Layout columns container - responsive flex that maintains width then stacks */
        [class*="bslib-grid"] {
            display: flex !important;
            gap: 8px !important;
            align-items: flex-start !important;
            flex-wrap: wrap !important;
        }
        
        /* Default: 4 buttons per row on wide screens - buttons grow to fill space */
        [class*="bslib-grid"] > * {
            flex: 1 1 auto !important;
            min-width: 220px !important;
            max-width: none !important;
            height: auto !important;
            max-height: none !important;
        }
        
        /* Ensure ALL wrapper layers can grow with content - target every level */
        [class*="bslib-grid"] > * > *,
        [class*="bslib-grid"] > * > * > *,
        [class*="bslib-grid"] > * > * > * > * {
            height: auto !important;
            max-height: none !important;
        }
        
        /* 2 buttons per row on medium screens */
        @media (max-width: 900px) {
            [class*="bslib-grid"] > * {
                flex: 1 1 auto !important;
                min-width: calc(50% - 8px) !important;
            }
        }
        
        /* 1 button per row on narrow screens */
        @media (max-width: 500px) {
            [class*="bslib-grid"] > * {
                flex: 1 1 auto !important;
                min-width: 100% !important;
            }
        }
        .option-button .markdown-content {
            width: 100% !important;
            height: auto !important;
            text-align: center !important;
            overflow-wrap: break-word !important;
            word-wrap: break-word !important;
            white-space: normal !important;
            display: block !important;
        }
        
        .option-button .markdown-content * {
            max-width: 100% !important;
        }
        
        /* Copy exact button styling to correct answer */
        .correct-answer-highlight .markdown-content {
            width: 100% !important;
            height: auto !important;
            text-align: center !important;
            overflow-wrap: break-word !important;
            word-wrap: break-word !important;
            white-space: normal !important;
            display: block !important;
        }
        
        .correct-answer-highlight .markdown-content * {
            max-width: 100% !important;
        }

        /* Ensure each solution-step card has a sensible minimum height
           but can grow as needed with its content. */
        .step-card {
            min-height: 100px !important;
        }

        /* ---------------- ANSWER CONTENT ----------------
           For the row that contains numeric input, units, combined answer, etc. */
        .answer-content > div {
            margin: 0 !important;
            padding: 8px !important;
            display: flex !important;
            align-items: center !important;
            gap: 10px !important;
        }

        /* 
           Additional form-group / selectize spacing 
        */
        .form-group {
            margin: 0 !important;
            padding: 0 !important;
        }
        .form-control, .selectize-control {
            margin: 0 !important;
            padding: 6px !important;
        }
        input[type="number"] {
            width: 100% !important;
            min-width: 80px !important;
        }
        #combined_answer {
            margin: 0 !important;
            padding: 6px !important;
        }

        /* ---------------- MARKDOWN / QUESTION TEXT ----------------
           For question bodies, solutions, etc. */
        .markdown-base {
            margin-top: -10px;
            font-family: 'Helvetica Neue', Arial, sans-serif !important;
            font-size: 1.1em !important;
            margin-bottom: 0px;
            padding: 0 -10px;
            color: #333 !important;
        }
        .main-question-content {
            margin-top: 25px;
            font-family: 'Helvetica Neue', Arial, sans-serif !important;
            font-size: 1.1em !important;
            margin-bottom: 10px;
            padding: -10px 10px;
            color: #333 !important;
        }
        .markdown-content {
            margin-top: 0px;
            padding: 0px -10px !important;
            font-family: 'Helvetica Neue', Arial, sans-serif !important;
            font-size: 1.1em !important;
            line-height: 1.6 !important;
            color: #333 !important;
        }
        .solution-markdown-content {
            margin-top: 20px;
            padding: 0px -10px !important;
            font-family: 'Helvetica Neue', Arial, sans-serif !important;
            font-size: 1.1em !important;
            line-height: 1.6 !important;
            color: #333 !important;
        }

        /* 
           Top-level h2 styling, e.g. .tutor-title
        */
        h2 {
            margin-bottom: 10;
            padding-bottom: 0px;
        }

        /* ---------------- QUESTION TYPE PILL BADGES ---------------- */
        .question-type-pill {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }
        .question-banner2 {
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
        }
        .pill-context { background-color: #6f42c1; color: white; }
        .pill-conceptual { background-color: #007bff; color: white; }
        .pill-algebraic { background-color: #fd7e14; color: white; }
        .pill-intermediate { background-color: #17a2b8; color: white; }
        .pill-vector { background-color: #20c997; color: white; }
        .pill-formula { background-color: #007bff; color: white; }
        .pill-algebraic { background-color: #fd7e14; color: white; }
        .pill-substitute { background-color: #17a2b8; color: white; }
        .pill-derivative { background-color: #e83e8c; color: white; }
        .pill-integral { background-color: #6610f2; color: white; }
        .pill-vector { background-color: #20c997; color: white; }
        .pill-force { background-color: #dc3545; color: white; }
        .pill-angle { background-color: #28a745; color: white; }
        .pill-kinematics { background-color: #ffc107; color: #333; }
        .pill-final { background-color: #28a745; color: white; }
        
        /* ---------------- LANDING PAGE STYLES ---------------- */
        .welcome-title {
            font-size: 36px;
            color: #333333;
            margin-top: 0;
            margin-bottom: 2px;
            text-align: center;
        }
        .welcome-subtitle {
            font-size: 18px;
            color: #666666;
            margin-bottom: 5px;
            text-align: center;
        }
        .section-button {
            border: 0;
            padding: 20px;
            font-size: 18px;
            border-radius: 10px;
            transition: background-color 0.2s ease, color 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease, filter 0.2s ease;
            cursor: pointer;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.12);
            text-align: center;
            font-weight: 600;
        }
        .section-button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 14px rgba(0, 0, 0, 0.16);
            filter: brightness(1.1);
        }
        .section-buttons-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            width: calc(100% - 40px);
            max-width: 95%;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        @media (min-width: 768px) {
            .section-buttons-container {
                grid-template-columns: repeat(2, 1fr);
                width: 98%;
                max-width: 98%;
            }
        }

        /* ---------------- Adjust Dropdown Menu ---------------- */
        /* Ensure the dropdown menu appears correctly (if any exist) */
        .navbar .dropdown-menu {
            right: 40;
            left: 0;
            align: right;
        }

        /* Optional: Style for feedback messages */
        .feedback-text {
            margin-top: 10px;
            font-size: 16px;
            color: #333;
            text-align: center;
        }

        /* ---------- MOBILE RESPONSIVE FIXES (minimal, appended) ---------- */

        /* 2) Fix landing page section buttons on phones */
        @media (max-width: 767px) {
          html, body {
            height: auto !important;
            overflow-y: auto !important;
          }
          .section-buttons-container {
            display: grid !important;
            grid-template-columns: 1fr !important;
            align-items: center !important;
            justify-content: flex-start !important;
            margin: 0 auto !important;
            gap: 12px !important;
          }
          .section-button {
            width: 100% !important;
            font-size: 16px !important;
            padding: 12px 10px !important;
          }
          .landing-container {
            height: auto !important;
            padding: 20px 0 !important;
            min-height: auto !important;
            overflow-y: auto !important;
          }
        }
        
        .card-prerender {
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.12s ease-out;
        }
        .card-prerender.ready {
            opacity: 1;
            visibility: visible;
        }

/* ==== Gray band behind input components (inset) ==== */
.answer-content {
    background: #f2f2f2 !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    margin-top: 6px !important;
}

.correct-answer-highlight {
    background: #f2f2f2 !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    margin-top: 6px !important;
}

/* Display math ($$) in correct answer should not add extra vertical spacing */
.correct-answer-highlight .katex-display {
    margin: 0 !important;
    padding: 0 !important;
}

/* Display math ($$) in analytics should not add extra vertical spacing */
.analytics-answer-cell .katex-display,
.analytics-step-detail .katex-display {
    margin: 0 !important;
    padding: 0 !important;
}

/* Allow app to shrink on very small screens */
html, body, .container, .container-fluid {
    min-width: 0 !important;
}

/* Inputs: horizontal when wide, stacked & centered when narrow */
@media (max-width: 760px) {
    .answer-content > div {
        flex-direction: column !important;
        align-items: center !important;
        gap: 10px !important;
    }

    .answer-content .form-control,
    .answer-content .form-select {
        width: 100% !important;
        max-width: 260px !important;
    }

    .answer-content .btn {
        width: 100% !important;
        max-width: 220px !important;
    }

    #combined_answer {
        text-align: center !important;
        justify-content: center !important;
    }
}

/* === Allow main menu to scroll on very small screens === */
@media (max-width: 760px) {
    html, body {
        height: auto !important;
        overflow-y: auto !important;
    }

    .container, .container-fluid {
        height: auto !important;
        overflow-y: auto !important;
    }

    /* Ensure main menu cards never get clipped */
    .main-menu,
    .main-menu-container,
    .main-menu .row {
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
    }
}

/* === MAIN MENU: prevent overflow off-screen on very small widths === */
@media (max-width: 760px) {
    .main-menu,
    .main-menu-container {
        min-height: 100svh !important;   /* mobile-safe viewport height */
        overflow-y: auto !important;
        align-content: flex-start !important;
    }
}

/* === MAIN MENU FINAL SAFETY FIX (visibility + background only) === */
@media (max-width: 760px) {
    .main-menu,
    .main-menu-container {
        min-height: 100svh !important;
        height: auto !important;
        overflow-y: auto !important;
        background: white !important;
        padding-bottom: 24px !important; /* ensure last card stays visible */
        justify-content: center !important;
    }
}

        /* Ensure landing/main menu fills and scrolls correctly on all screen sizes */
        .landing-container {
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: flex-start !important;
            height: auto !important;
            padding: 20px !important;
            padding-top: 75px !important;
            background-color: transparent !important;
        }
        
        @media (min-width: 768px) {
            .landing-container {
                padding-top: 75px !important;
            }
        }

/* Vertically & horizontally center ONLY main-menu section buttons */
.landing-container .section-buttons-container .section-button {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Ensure page only grows to content size, not full viewport */
body, html {
    height: auto !important;
    min-height: 0 !important;
}

.container-fluid, .container {
    height: auto !important;
    min-height: 0 !important;
}

#main_ui {
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
}

/* Prevent Shiny outputs from adding extra height */
.shiny-html-output {
    height: auto !important;
    min-height: 0 !important;
}

/* Override any Bootstrap or Shiny container height */
.bslib-page-fluid, .page-fluid, [class*="container"] {
    height: auto !important;
    min-height: 0 !important;
}

/* Specifically target the main wrapper divs */
body > div, body > div > div {
    height: auto !important;
    min-height: 0 !important;
}

/* Ensure no flex-grow on the body wrapper */
.page-fluid > * {
    flex-grow: 0 !important;
    flex-shrink: 0 !important;
}

/* Prevent content from causing container expansion */
.page-fluid {
    display: block !important;
}

/* Force all Shiny containers to not expand */
.bslib-page-fluid, .bslib-page-fluid > *, body > div, body > div > div {
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
}
"""
    ),
        ui.tags.style(r"""
        /* ===================================================================
           MANTINE-INSPIRED THEME LAYER (blue accent, light) + Iconify
           Appended last so it overrides earlier rules. Scoped to
           buttons / cards / inputs / pills / notifications only.
           =================================================================== */
        :root {
            --mnt-blue: #228be6;
            --mnt-blue-hover: #1c7ed6;
            --mnt-blue-light: #e7f5ff;
            --mnt-radius: 8px;
            --mnt-border: #dee2e6;
            --mnt-text: #212529;
            --mnt-dimmed: #868e96;
            --mnt-font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            --mnt-shadow-sm: 0 1px 3px rgba(0,0,0,.05), 0 1px 2px rgba(0,0,0,.06);
            --mnt-shadow-md: 0 1px 3px rgba(0,0,0,.05), 0 10px 15px -5px rgba(0,0,0,.05), 0 7px 7px -5px rgba(0,0,0,.04);
        }

        body, .tutor-title, .question-title, .question-title2,
        .markdown-content, .markdown-base, .solution-markdown-content,
        button, input, select, .form-control, .selectize-input {
            font-family: var(--mnt-font) !important;
        }
        body { color: var(--mnt-text); }

        /* Iconify baseline alignment */
        iconify-icon { display: inline-block; vertical-align: -0.14em; line-height: 1; }

        /* --- Paper / cards (Mantine Paper) --- */
        .card, .step-card {
            border: 1px solid var(--mnt-border) !important;
            border-radius: var(--mnt-radius) !important;
            box-shadow: var(--mnt-shadow-sm) !important;
        }
        .card:hover { box-shadow: var(--mnt-shadow-md) !important; }

        /* --- Primary / Submit button (Mantine filled) --- */
        .btn-primary {
            background-color: var(--mnt-blue) !important;
            border: 1px solid var(--mnt-blue) !important;
            color: #fff !important;
            border-radius: var(--mnt-radius) !important;
            font-weight: 600 !important;
            text-transform: none !important;
            letter-spacing: normal !important;
            box-shadow: none !important;
            transition: background-color .15s ease, transform .05s ease !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
        }
        .btn-primary:hover {
            background-color: var(--mnt-blue-hover) !important;
            border-color: var(--mnt-blue-hover) !important;
            color: #fff !important;
        }
        .btn-primary:active { transform: translateY(1px); }
        .btn-primary iconify-icon { font-size: 18px; }

        /* --- Inputs (Mantine TextInput / Select) --- */
        input[type="number"], .form-control, .selectize-input,
        select, select.form-select {
            border: 1px solid var(--mnt-border) !important;
            border-radius: var(--mnt-radius) !important;
            transition: border-color .1s ease, box-shadow .1s ease !important;
        }
        input[type="number"]:focus, .form-control:focus,
        .selectize-input.focus, select:focus {
            border-color: var(--mnt-blue) !important;
            box-shadow: 0 0 0 1px var(--mnt-blue) !important;
            outline: none !important;
        }

        /* --- Step pills (Mantine SegmentedControl / pill) --- */
        .question_steps .nav-pills .nav-link {
            border-radius: var(--mnt-radius) !important;
            font-weight: 600 !important;
            transition: all .15s ease !important;
        }

        /* --- Section buttons: keep per-section colour, add Mantine polish + icon --- */
        .section-button {
            border-radius: var(--mnt-radius) !important;
            font-weight: 600 !important;
            border: none !important;
            box-shadow: var(--mnt-shadow-sm) !important;
            transition: transform .1s ease, box-shadow .15s ease, filter .15s ease !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
            text-transform: none !important;
        }
        .section-button:hover {
            transform: translateY(-1px);
            box-shadow: var(--mnt-shadow-md) !important;
            filter: brightness(1.04);
        }
        .section-button iconify-icon { font-size: 20px; opacity: .9; }

        /* --- Header / footer text buttons (Mantine subtle) --- */
        .header-main-menu-btn, .footer-btn {
            border-radius: var(--mnt-radius) !important;
            font-weight: 600 !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 6px !important;
            transition: background-color .12s ease !important;
        }
        .header-main-menu-btn:hover, .footer-btn:hover {
            background-color: var(--mnt-blue-light) !important;
        }
        .header-main-menu-btn iconify-icon,
        .footer-btn iconify-icon { font-size: 18px; }

        /* --- Notifications (Mantine Notification) --- */
        .shiny-notification {
            border-radius: var(--mnt-radius) !important;
            box-shadow: var(--mnt-shadow-md) !important;
            border: 1px solid var(--mnt-border) !important;
        }

        /* --- Mobile: full-width tap targets, scaled icons --- */
        @media (max-width: 767px) {
            .section-button { width: 100% !important; }
            .section-button iconify-icon { font-size: 18px; }
            .btn-primary {
                width: 100% !important;
                justify-content: center !important;
                padding: 12px 16px !important;
                height: auto !important;
            }
            .header-main-menu-btn, .footer-btn { justify-content: flex-start !important; }
        }
        """),
    )

)

def get_question_seed(section, question, subq):
    """Generate a consistent seed for a given question and sub-question"""
    return hash(f"{section}_{question}_{subq}") & 0xFFFFFFFF

def server(input, output, session):
    csv_data = reactive.Value("")

    @reactive.Effect
    @reactive.event(input.loaded_csv)
    def _():
        csv_data.set(input.loaded_csv() or "")

    def log_response(user_id, timestamp, section, question_number, step, action, details):
        # Use proper CSV formatting to handle commas in fields
        import io
        import csv as csv_module
        
        current = csv_data()
        if not current.strip():
            current = "user_id,timestamp,section,question_number,step,action,details\n"
        
        # Create a properly formatted CSV row
        output = io.StringIO()
        writer = csv_module.writer(output)
        writer.writerow([user_id, timestamp, section, question_number, step, action, details])
        row = output.getvalue()
        
        csv_data.set(current + row)
    
    # Watch for csv_data changes and send to localStorage
    @reactive.Effect
    @reactive.event(csv_data)
    async def _save_csv():
        if csv_data():
            await session.send_custom_message('save_csv', {'csv': csv_data()})

    # Reactive value to show session data modal
    show_session_data = reactive.Value(False)

    # Observer for view session data button
    @reactive.Effect
    @reactive.event(input.view_session_data)
    def _():
        show_session_data.set(True)
        # Show modal with session data
        import io
        if csv_data().strip():
            try:
                # Clean the CSV data the same way we clean the main CSV
                content = csv_data()
                content = content.replace('\r\n', '\n').replace('\r', '\n')
                # Use Python engine - no need to skip bad lines now that we're properly formatting
                df_data = pd.read_csv(io.StringIO(content), engine='python')
                user_data = df_data[df_data['user_id'] == session.id]
            except Exception as e:
                # If parsing fails, show error message
                ui.modal_show(
                    ui.modal(
                        ui.div(
                            ui.p(f"Error reading session data: {str(e)}"),
                            ui.p("The data may be corrupted."),
                        ),
                        title="Session Data Error",
                        easy_close=True,
                        footer=ui.modal_button("Close")
                    )
                )
                return
            if not user_data.empty:
                table_html = user_data.to_html(index=False, classes='table table-striped table-sm')
                ui.modal_show(
                    ui.modal(
                        ui.div(
                            ui.h4("Your Session Data"),
                            ui.div(
                                ui.HTML(table_html),
                                style="max-height: 500px; overflow-y: auto; overflow-x: auto;"
                            ),
                        ),
                        title="Session Interactions",
                        easy_close=True,
                        footer=ui.modal_button("Close"),
                        size="xl"
                    )
                )
            else:
                ui.modal_show(
                    ui.modal(
                        ui.div(
                            ui.p("No data logged yet for this session."),
                        ),
                        title="Session Interactions",
                        easy_close=True,
                        footer=ui.modal_button("Close")
                    )
                )
        else:
            ui.modal_show(
                ui.modal(
                    ui.div(
                        ui.p("No data file found."),
                    ),
                    title="Session Interactions",
                    easy_close=True,
                    footer=ui.modal_button("Close")
                )
            )
    current_order = reactive.Value([])
    current_section = reactive.Value("")
    current_question = reactive.Value("")
    current_subq = reactive.Value(0)
    show_solution = reactive.Value(False)
    feedback_text = reactive.Value("")
    current_answer = reactive.Value(None)
    current_units = reactive.Value("Select units")

    def reset_state():
        current_subq.set(0)
        show_solution.set(False)
        feedback_text.set("")
        current_answer.set(None)
        current_units.set("Select units")

    # **Helper Function to Create Observers for Landing Page Section Buttons**
    def create_section_observer(button_id, section):
        @reactive.Effect
        @reactive.event(input[button_id])
        async def _(_section=section):
            # Action buttons increment their value on click
            if input[button_id]() > 0:
                # Set current section and mark that we are now in a section view
                current_section.set(_section)
                is_section_selected.set(True)
                reset_state()

                # Immediately select that section's first question
                section_questions = df()[df()["section"] == _section]
                unique_questions = section_questions.drop_duplicates("question_number")
                if not unique_questions.empty:
                    current_question.set(unique_questions.iloc[0]["main_question"])

                # Log the section selection
                user_id = session.id
                timestamp = datetime.now().isoformat()
                log_response(user_id, timestamp, _section, '', '', 'section_selected', _section)

                # Show a notification
                await show_new_notification(
                    f"Section '{_section}' selected. Let's begin!",
                    duration=3,
                    notif_type="message"
                )

    # **Create Observers for All Landing Page Section Buttons**
    for section in sections:
        button_id = f"section_button_{sanitize_id(section)}"
        create_section_observer(button_id, section)
    
    # **Analytics Button Observer**
    @reactive.Effect
    @reactive.event(input.analytics_button)
    def _():
        if input.analytics_button() > 0:
            show_analytics.set(True)
            is_section_selected.set(False)

    @output
    @render.ui
    def main_ui():
        # Common header used on both the main menu and the question view
        header = ui.div(
            ui.div(
                ui.HTML(f'''
                <div style="display: flex; align-items: center; gap: 12px;">
                    <img src="icon.png?v={cache_buster()}" width="32" height="32" alt="Icon" style="display: block;">
                    <h2 class="tutor-title" style="margin: 0;">Biomechanics Tutor</h2>
                </div>
                '''),
                class_="title-container"
            ),
            ui.div(
                ui.tags.div(
                    ui.tags.span(),
                    ui.tags.span(),
                    ui.tags.span(),
                    class_="hamburger-menu",
                    onclick="toggleMobileMenu()"
                ),
                ui.div(
                    ui.input_action_button(
                        "back_to_menu",
                        ui.HTML('<iconify-icon icon="tabler:home"></iconify-icon><span>Main Menu</span>'),
                        class_="btn btn-link header-main-menu-btn"
                    ),
                    ui.input_action_button(
                        "analytics_button",
                        ui.HTML('<iconify-icon icon="tabler:chart-bar"></iconify-icon><span>My Performance</span>'),
                        class_="btn btn-link header-main-menu-btn"
                    ),
                    class_="header-buttons",
                    id="headerButtons"
                ),
                style="display: flex; align-items: center; gap: 10px;"
            ),
            class_="tutor-header"
        )

        # Footer with data buttons
        footer = ui.div(
            ui.download_button("download_my_session", ui.HTML('<iconify-icon icon="tabler:download"></iconify-icon><span>Download My Session Data</span>'), class_="btn btn-link footer-btn"),
            class_="tutor-footer",
            style="position: fixed; bottom: 0; left: 0; right: 0; width: 100%; margin: 0; padding-left: 16px; padding-right: 16px; z-index: 100;" if show_analytics() else None
        )

        if show_analytics():
            body = ui.div(
                ui.output_ui("analytics_view"),
                class_="analytics-wrapper",
                style="position: fixed; top: 65px; left: 0; right: 0; bottom: 60px; overflow-y: auto; overflow-x: hidden; z-index: 10; background: #e0e0e0;"
            )
        elif not is_section_selected():
            body = landing_page_ui
        else:
            body = ui.div(
                ui.output_ui("question_nav"),
                ui.output_ui("question_card"),
                ui.output_ui("main_content"),
                ui.output_ui("solution_card"),
            )

        return ui.div(
            header,
            body,
            footer,
            id="main-wrapper",
            style="height: 100vh; overflow: hidden;" if show_analytics() else None
        )

    # Allow user to return to the main menu from the header link
    @reactive.Effect
    @reactive.event(input.back_to_menu)
    def _go_back_to_menu():
        is_section_selected.set(False)
        show_analytics.set(False)
        current_section.set("")
        current_question.set("")
        reset_state()

    # **Section Indicator Output**
    @output
    @render.text
    def current_section_indicator():
        if not current_section():
            return "Please select a section from the menu"
        return f"Current Section: {current_section()}"

    @output
    @render.ui
    def question_nav():
        if not current_section():
            return None

        section_questions = df()[df()["section"] == current_section()]
        unique_questions = section_questions.drop_duplicates("question_number")

        nav_items = []
        for _, row in unique_questions.iterrows():
            nav_items.append(
                ui.nav_panel(f"{row['question_number']}", value=row["main_question"])
            )

        return ui.div(
            ui.navset_tab(*nav_items, id="question", selected=current_question()),
            class_="question_tabs"
        )

    @reactive.Effect
    @reactive.event(input.question)
    def _():
        if input.question() and input.question() != current_question():
            current_question.set(input.question())
            reset_state()

    @output
    @render.ui
    async def question_card():
        if not current_section() or not current_question():
            return None

        q_data = df()[
            (df()["section"] == current_section())
            & (df()["main_question"] == current_question())
        ]
        if q_data.empty:
            return None

        main_row = q_data.iloc[0]

        top_content = [
            ui.div(
                ui.h3(
                    f"{current_section()} {main_row['question_number']}",
                    class_="question-title"
                ),
                class_="question-banner"
            ),
            ui.div(
                "",
                class_="markdown-base main-question-content",
                id="full-question",
                style="visibility:hidden;",
                **{"data-markdown": main_row["full_question"]}
            ),
        ]

        # Use the CSV path as-is (absolute or relative) with cache-busting
        if pd.notna(main_row["image_url"]):
            image_url = main_row["image_url"]
            # Add cache-busting parameter
            separator = '&' if '?' in image_url else '?'
            image_url_with_cache = f"{image_url}{separator}v={cache_buster()}"
            top_content.append(
                ui.tags.img(
                    src=image_url_with_cache,
                    style="max-height: 300px; width: auto; max-width: 100%; height: auto; margin: 10px -15px;",
                )
            )

        units_options = [
            "Select units", "m/s", "m/s²", "rad/s", "rad/s²", "N",
            "N/m", "kg", "m", "J", "W", "No units", "s", "Degrees",
            "Revolutions", "RPM", "N·m", "kg·m²", "kg·m/s"
        ]

        bottom_content = ui.div(
            ui.div(
                ui.input_numeric("numeric_answer", "", value=0),
                ui.input_select("units_answer", "", units_options, selected="Select units"),
                ui.output_text("combined_answer"),
                ui.input_action_button(
                    "submit_answer",
                    ui.HTML('<iconify-icon icon="tabler:circle-check"></iconify-icon><span>Submit</span>'),
                    class_="btn-primary"
                ),
                style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;",
            ),
            class_="answer-content"
        )

        # Minimal functional change: ensure DOM exists on first load before rendering markdown
        if initial_load():
            initial_load.set(False)

        await session.send_custom_message(
            "render-card",
            {"cardSelector": "#question_card_outer", "contentSelector": "[data-markdown]"},
        )

        return ui.div(
            ui.card(
                ui.div(*top_content, style="padding-top: 10px;"), 
                ui.div(bottom_content, style="padding-bottom: 10px;"), 
                style="margin-bottom: 10px;",
            ),
            class_="card-prerender",
            id="question_card_outer",
        )

    @output
    @render.ui
    async def main_content():
        if not current_section() or not current_question():
            return None

        q_data = df()[
            (df()["section"] == current_section())
            & (df()["main_question"] == current_question())
        ]
        sub_questions = list(q_data["sub_question"].unique())

        nav_panels = []
        for i, sq in enumerate(sub_questions):
            sq_data = q_data[q_data["sub_question"] == sq]
            subq_id = f"subq-{i}"
            
            # Get question type for this sub-question
            question_type = sq_data.iloc[0].get("question_type", "")
            
            # Map question type to pill class (10 categories)
            pill_class = "pill-substitute"
            pill_text = ""
            if "Formula Selection" in question_type:
                pill_class = "pill-formula"
                pill_text = "Formula"
            elif "Algebraic Manipulation" in question_type:
                pill_class = "pill-algebraic"
                pill_text = "Algebraic"
            elif "Substitute" in question_type:
                pill_class = "pill-substitute"
                pill_text = "Calculate"
            elif "Derivative" in question_type:
                pill_class = "pill-derivative"
                pill_text = "Derivative"
            elif "Integral" in question_type:
                pill_class = "pill-integral"
                pill_text = "Integral"
            elif "Vector" in question_type:
                pill_class = "pill-vector"
                pill_text = "Vector"
            elif "Force" in question_type:
                pill_class = "pill-force"
                pill_text = "Force"
            elif "Angle" in question_type:
                pill_class = "pill-angle"
                pill_text = "Angle"
            elif "Kinematics" in question_type:
                pill_class = "pill-kinematics"
                pill_text = "Kinematics"
            elif "Final Answer" in question_type:
                pill_class = "pill-final"
                pill_text = "Final"

            if i == current_subq():
                options = []
                for j in range(4):
                    option_text = sq_data.iloc[0][f"option_{j+1}"]
                    # Minimal functional fix: skip NaN/blank/none options so last step shows no cards
                    if pd.isna(option_text) or str(option_text).strip().lower() in ("", "nan", "none"):
                        continue

                    # Check if it's an image (either URL or file path ending with image extension)
                    option_text_str = str(option_text)
                    is_image = (option_text_str.startswith(("http://", "https://")) or 
                               option_text_str.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')))
                    
                    if is_image:
                        # Add cache-busting to option images
                        separator = '&' if '?' in option_text_str else '?'
                        option_image_url = f"{option_text_str}{separator}v={cache_buster()}"
                        button_content = ui.tags.img(
                            src=option_image_url,
                            style="max-height: 300px; width: auto; max-width: 100%; height: auto;",
                        )
                    else:
                        button_content = ui.div(
                            "",
                            class_="markdown-content",
                            id=f"opt_{i}_{j}-content",
                            **{"data-markdown": option_text}
                        )
                    options.append(
                        {
                            "content": button_content,
                            "option_text": option_text,
                            "feedback": sq_data.iloc[0][f"feedback_{j+1}"],
                            "index": j,
                            "original_index": j + 1,
                            "is_correct": sq_data.iloc[0]["correct_option"] == (j + 1),
                        }
                    )
                random.seed(get_question_seed(current_section(), current_question(), sq))
                random.shuffle(options)
                current_order.set(options)

                subq_content = [
                    ui.div(
                        "",
                        class_="markdown-content",
                        id=subq_id,
                        **{"data-markdown": sq}
                    ),
                ]
                if options:
                    subq_content.append(
                        ui.layout_columns(*[
                            ui.input_action_button(
                                f"opt_{i}_{idx}",
                                opt["content"],
                                class_="btn-block option-button",
                            )
                            for idx, opt in enumerate(options)
                        ])
                    )

                content = [
                    ui.card(
                        ui.div(
                            ui.h3("Solution Steps", class_="question-title2"),
                            ui.HTML(f'<span class="question-type-pill {pill_class}">{pill_text}</span>') if pill_text else ui.span(),
                            class_="question-banner2"
                        ),
                        *subq_content,
                        class_="step-card"
                    )
                ]
            else:
                content_elements = [
                    ui.div(
                        ui.h3("Solution Steps", class_="question-title2"),
                        ui.HTML(f'<span class="question-type-pill {pill_class}">{pill_text}</span>') if pill_text else ui.span(),
                        class_="question-banner2"
                    ),
                    ui.div(
                        "",
                        class_="markdown-content",
                        id=subq_id,
                        **{"data-markdown": sq}
                    ),
                ]
                if i < current_subq():
                    # Get the correct option for this step
                    correct_option_index = sq_data.iloc[0]["correct_option"]
                    if pd.notna(correct_option_index):
                        correct_option_text = sq_data.iloc[0][f"option_{int(correct_option_index)}"]
                        
                        # Check if the correct answer is an image
                        correct_option_text_str = str(correct_option_text)
                        is_correct_image = (correct_option_text_str.startswith(("http://", "https://")) or 
                                           correct_option_text_str.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')))
                        
                        if is_correct_image:
                            # Add cache-busting to correct answer images
                            separator = '&' if '?' in correct_option_text_str else '?'
                            correct_image_url = f"{correct_option_text_str}{separator}v={cache_buster()}"
                            content_elements.append(
                                ui.div(
                                    ui.tags.img(
                                        src=correct_image_url,
                                        style="max-height: 300px; width: auto; max-width: 100%; height: auto;",
                                    ),
                                    class_="correct-answer-highlight",
                                    style="display: flex; justify-content: center;"
                                )
                            )
                        else:
                            content_elements.append(
                                ui.div(
                                    "",
                                    class_="markdown-content correct-answer-highlight",
                                    **{"data-markdown": correct_option_text}
                                )
                            )
                
                content = [
                    ui.card(
                        *content_elements,
                        class_="step-card"
                    )
                ]

            nav_panels.append(
                ui.nav_panel(f"Step {i+1}", *content)
            )

        await session.send_custom_message(
            "render-card",
            {"cardSelector": "#main_content_outer", "contentSelector": "[data-markdown]"},
        )

        return ui.div(
            ui.div(
                ui.navset_pill(
                    *nav_panels,
                    id="question_steps",
                    selected=f"Step {current_subq() + 1}",
                ),
                class_="question_steps"
            ),
            class_="card-prerender",
            id="main_content_outer",
        )

    # === Separate solution card (appears only when show_solution() is True) ===
    @output
    @render.ui
    async def solution_card():
        if not show_solution():
            return None

        q_data = df()[
            (df()["section"] == current_section())
            & (df()["main_question"] == current_question())
        ]
        if q_data.empty or pd.isna(q_data.iloc[0]["solution"]):
            return None

        row = q_data.iloc[0]

        # Light-touch cleanup for nicer Markdown structure; does not alter styling rules
        solution_text = str(row["solution"]).replace("---", "<hr>")
        solution_text = solution_text.replace("\n", "  \n")

        # Trigger card-level prerender for solution block
        await session.send_custom_message(
            "render-card",
            {"cardSelector": "#solution_card_outer", "contentSelector": "[data-markdown]"},
        )

        return ui.div(
            ui.card(
                ui.div(
                    ui.h3("Solution", class_="question-title"),
                    ui.tags.div(
                        "",
                        class_="solution-markdown-content",
                        id="solution-content",
                        **{"data-markdown": solution_text},
                    ),
                    style="margin-top: 15px;"
                ),
                style="margin-bottom: 10px;"
            ),
            class_="card-prerender",
            id="solution_card_outer",
        )

    @output
    @render.text
    def combined_answer():
        if input.numeric_answer() is not None and input.units_answer() != "Select units":
            return f"{input.numeric_answer()} {input.units_answer()}"
        elif input.numeric_answer() is not None:
            return f"{input.numeric_answer()} (no units selected)"
        return ""

    async def show_new_notification(msg, *, duration=5, notif_type="message"):
        old_id = last_notification_id()
        if old_id is not None:
            ui.notification_remove(old_id)
            last_notification_id.set(None)

        # Wrap message in a div with class for math rendering
        wrapped_msg = f'<div class="notification-math">{msg}</div>'
        new_id = ui.notification_show(
            ui.HTML(wrapped_msg),
            duration=duration,
            type=notif_type
        )
        last_notification_id.set(new_id)
        
        # Trigger math rendering in the notification
        await session.send_custom_message(
            'render-math', {'selector': '.notification-math'}
        )

    def create_option_observer(sub_q, opt):
        @reactive.Effect
        @reactive.event(input[f"opt_{sub_q}_{opt}"])
        async def _():
            q_data = df()[
                (df()["section"] == current_section())
                & (df()["main_question"] == current_question())
            ]
            sub_questions = list(q_data["sub_question"].unique())
            if sub_q >= len(sub_questions):
                return  # Prevent index out of range
            sub_q_data = q_data[q_data["sub_question"] == sub_questions[sub_q]]
            options = current_order()
            if opt >= len(options):
                return  # Prevent index out of range
            clicked_option = options[opt]
            feedback_message = sub_q_data.iloc[0][
                f"feedback_{clicked_option['original_index']}"
            ]
            is_correct = (
                clicked_option["original_index"]
                == sub_q_data.iloc[0]["correct_option"]
            )

            # Log the option selection
            user_id = session.id
            timestamp = datetime.now().isoformat()
            question_number = sub_q_data.iloc[0]["question_number"]
            step = sub_q + 1
            action = "option_selected"
            # Include full question and answer text in details (no truncation)
            question_text = sub_questions[sub_q]
            answer_text = str(clicked_option['option_text'])
            details = f"Q: {question_text} | A: {answer_text} | correct={is_correct}"
            log_response(user_id, timestamp, current_section(), question_number, step, action, details)

            if is_correct and current_subq() < len(sub_questions) - 1:
                current_subq.set(current_subq() + 1)
                await session.send_custom_message(
                    'render-math', {'selector': f'#subq-{current_subq()}'}
                )
                await show_new_notification("Correct! Moving to next step.", duration=3, notif_type="message")
            elif is_correct:
                await show_new_notification("Correct! Please enter your final answer.", duration=3, notif_type="message")
            else:
                await show_new_notification(feedback_message, duration=5, notif_type="warning")

    # **Create Observers for All Option Buttons**
    for i in range(20):  # Increased to support up to 20 steps
        for j in range(4):
            create_option_observer(i, j)

    # **Answer Submission Observer**
    @reactive.Effect
    @reactive.event(input.submit_answer)
    async def check_numeric():
        if input.numeric_answer() is None:
            feedback_text.set("")
            return

        current_answer.set(input.numeric_answer())
        current_units.set(input.units_answer())

        q_data = df()[
            (df()["section"] == current_section())
            & (df()["main_question"] == current_question())
        ]
        if q_data.empty:
            return

        # Ensure min and max are in correct order (handles negative ranges)
        min_val = float(q_data.iloc[0]["min_value"])
        max_val = float(q_data.iloc[0]["max_value"])
        correct_range = [min(min_val, max_val), max(min_val, max_val)]
        
        selected_units = input.units_answer()
        correct_units = normalize_units(q_data.iloc[0]["units"])

        numeric_correct = correct_range[0] <= input.numeric_answer() <= correct_range[1]
        units_correct = selected_units == correct_units

        # Log the answer submission
        user_id = session.id
        timestamp = datetime.now().isoformat()
        question_number = q_data.iloc[0]["question_number"]
        step = len(q_data["sub_question"].unique())  # Final step
        action = "answer_submitted"
        details = f"answer={input.numeric_answer()} {selected_units}, correct={numeric_correct and units_correct}"
        log_response(user_id, timestamp, current_section(), question_number, step, action, details)

        if numeric_correct and units_correct:
            show_solution.set(True)
            feedback_text.set("Correct! View the complete solution below.")
            await show_new_notification(
                "Correct! You can now view the complete solution.",
                duration=5,
                notif_type="message",
            )
            await session.send_custom_message('render-math', {'selector': '#solution-content'})
        elif numeric_correct and not units_correct:
            show_solution.set(False)
            if selected_units == "Select units":
                msg = "Your numeric answer is correct! Please select the appropriate units."
            else:
                msg = "Your numeric answer is correct, but the units are incorrect. Try again!"
            feedback_text.set(msg)
            await show_new_notification(msg, duration=5, notif_type="warning")
        else:
            show_solution.set(False)
            feedback_text.set("Try again. Your answer is not within the acceptable range.")
            await show_new_notification(
                "Try again. Your answer is not within the acceptable range.",
                duration=5,
                notif_type="warning",
            )

    # **Feedback Display Output**
    @output
    @render.text
    def feedback_display():
        return feedback_text()

    # **Analytics View**
    @output
    @render.ui
    def analytics_view():
        import io
        if not csv_data().strip():
            return ui.div(
                ui.h2("No Performance Data Yet"),
                ui.p("Complete some questions to see your performance analytics!"),
                style="text-align: center; padding: 50px;"
            )
        
        try:
            # Parse CSV data
            content = csv_data()
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            df_data = pd.read_csv(io.StringIO(content), engine='python')
            user_data = df_data[df_data['user_id'] == session.id]
            
            if user_data.empty:
                return ui.div(
                    ui.h2("No Performance Data Yet"),
                    ui.p("Complete some questions to see your performance analytics!"),
                    style="text-align: center; padding: 50px;"
                )
            
            # Extract answer submissions only
            answers = user_data[user_data['action'] == 'answer_submitted'].copy()
            
            # Extract option selections
            options = user_data[user_data['action'] == 'option_selected'].copy()
            
            # Parse correctness from details
            options['correct'] = options['details'].str.contains('correct=True')
            answers['correct'] = answers['details'].str.contains('correct=True')
            
            # Combine all attempts (options + answer submissions) for comprehensive tracking
            all_attempts = pd.concat([options, answers], ignore_index=True).sort_values('timestamp')
            
            # Add attempt numbering: group by section+question, detect breaks (new attempt sessions)
            # A new attempt starts when:
            # 1. Step 1 appears after progressing past step 1, OR
            # 2. Step 1 appears after submitting a final answer, OR
            # 3. answer_submitted appears after a previous answer_submitted
            all_attempts['attempt_num'] = 0
            for (section, question), group in all_attempts.groupby(['section', 'question_number'], sort=False):
                indices = group.index
                attempt = 1
                max_option_step_seen = 0  # Track highest step from option selections
                answer_submitted_count = 0  # Count how many answers have been submitted
                for idx in indices:
                    current_step = all_attempts.loc[idx, 'step']
                    current_action = all_attempts.loc[idx, 'action']
                    
                    # Check if this is a new attempt
                    is_new_attempt = False
                    
                    # New attempt if: step 1 appears after we've made progress
                    if current_step == 1 and current_action == 'option_selected':
                        if max_option_step_seen > 1 or answer_submitted_count > 0:
                            is_new_attempt = True
                    
                    # New attempt if: answer submitted after a previous answer was submitted
                    if current_action == 'answer_submitted' and answer_submitted_count > 0:
                        is_new_attempt = True
                    
                    # Apply new attempt
                    if is_new_attempt:
                        attempt += 1
                        max_option_step_seen = 0
                        answer_submitted_count = 0
                    
                    # Update tracking variables AFTER assigning attempt number
                    all_attempts.loc[idx, 'attempt_num'] = attempt
                    
                    # Update state for next iteration
                    if current_action == 'option_selected':
                        max_option_step_seen = max(max_option_step_seen, current_step)
                    elif current_action == 'answer_submitted':
                        answer_submitted_count += 1
            
            # Group by section and question for breakdown
            question_breakdown = all_attempts.groupby(['section', 'question_number', 'correct']).size().unstack(fill_value=0)
            
            # Calculate section-level statistics
            section_stats = all_attempts.groupby('section')['correct'].agg(['sum', 'count']).reset_index()
            section_stats.columns = ['section', 'correct', 'total']
            section_stats['incorrect'] = section_stats['total'] - section_stats['correct']
            section_stats['percentage'] = (section_stats['correct'] / section_stats['total'] * 100).round(1)
            
            # Section colors for visual consistency
            section_colors = {
                'Basic Math': '#007bff',
                'Calculus': '#fd7e14',
                'Trigonometry': '#17a2b8',
                'Force Resolution': '#e83e8c',
                'Linear Kinematics': '#6610f2',
                'Impulse Momentum': '#20c997',
                'Friction': '#dc3545',
                'Static Equilibrium': '#28a745',
                'Angular Kinematics': '#ffc107',
                'Work Energy Power': '#6c757d',
            }
            
            # Build bar chart HTML with clickable sections and question breakdowns
            chart_bars = []
            global_detail_counter = 0  # Global counter to ensure unique IDs across all sections
            for idx, row in section_stats.iterrows():
                correct_pct = (row['correct'] / row['total'] * 100)
                incorrect_pct = (row['incorrect'] / row['total'] * 100)
                section_name = row['section']
                color = section_colors.get(section_name, '#6c757d')
                
                # Get question breakdown for this section with step details
                section_questions = question_breakdown.loc[section_name] if section_name in question_breakdown.index else pd.DataFrame()
                question_rows = []
                if not section_questions.empty:
                    for q_num, q_row in section_questions.iterrows():
                        # Get step-by-step details for this question (both options and final answer)
                        question_attempts = all_attempts[(all_attempts['section'] == section_name) & (all_attempts['question_number'] == q_num)]
                        
                        # Group by attempt number to show separate attempts
                        for attempt_num, attempt_group in question_attempts.groupby('attempt_num'):
                            global_detail_counter += 1
                            detail_id = f"section_detail_{global_detail_counter}"
                            
                            step_badges = []
                            step_details = []
                            
                            for _, attempt_row in attempt_group.iterrows():
                                step_bg = '#28a745' if attempt_row['correct'] else '#dc3545'
                                if attempt_row['action'] == 'answer_submitted':
                                    # Use T for True (correct) and F for False (incorrect)
                                    step_label = 'T' if attempt_row['correct'] else 'F'
                                    step_type = 'Final Answer'
                                else:
                                    step_label = str(int(attempt_row['step']))
                                    step_type = f"Step {int(attempt_row['step'])}"
                                
                                step_badges.append(f"<span style='display: inline-block; background: {step_bg}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; margin-left: 6px; font-weight: 600; min-width: 28px; text-align: center;'>{step_label}</span>")
                                
                                # Extract question and answer from details
                                details_str = attempt_row['details']
                                question_text = ""
                                answer_text = ""
                                
                                if attempt_row['action'] == 'option_selected':
                                    # Format: "Q: ... | A: ... | correct=..."
                                    if 'Q: ' in details_str and 'A: ' in details_str:
                                        q_part = details_str.split('Q: ')[1].split(' | A: ')[0] if ' | A: ' in details_str else ""
                                        a_part = details_str.split('A: ')[1].split(' | correct=')[0] if ' | correct=' in details_str else details_str.split('A: ')[1]
                                        question_text = q_part
                                        answer_text = a_part
                                elif attempt_row['action'] == 'answer_submitted':
                                    # Format: "answer=X units, correct=..."
                                    if 'answer=' in details_str:
                                        answer_text = details_str.split('answer=')[1].split(', correct=')[0] if ', correct=' in details_str else details_str.split('answer=')[1]
                                        question_text = "Final numerical answer"
                                
                                result_icon = "✓" if attempt_row['correct'] else "✗"
                                result_color = "#28a745" if attempt_row['correct'] else "#dc3545"
                                
                                step_details.append(f"""
                                <div style='padding: 10px; margin: 5px 0; background: white; border-radius: 4px; border-left: 3px solid {step_bg};'>
                                    <div style='font-weight: 600; color: {step_bg}; margin-bottom: 5px;'>{step_type} <span style='color: {result_color}; margin-left: 8px;'>{result_icon}</span></div>
                                    {f"<div style='margin: 5px 0; color: #666; font-size: 0.95em;'><strong>Question:</strong> <span class='analytics-step-detail'>{question_text}</span></div>" if question_text else ""}
                                    <div style='margin: 5px 0; color: #333;'><strong>Answer:</strong> <span class='analytics-step-detail'>{answer_text}</span></div>
                                </div>
                                """)
                            
                            question_rows.append(f"""
                            <div style='margin: 5px 0;'>
                                <div style='padding: 8px 15px; border-left: 3px solid {color}; background: #f9f9f9; border-radius: 4px; cursor: pointer; user-select: none;' onclick='toggleDetail_{detail_id}()'>
                                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                                        <div>
                                            <span id='arrow_{detail_id}' style='display: inline-block; transition: transform 0.2s; margin-right: 8px;'>▶</span>
                                            <span style='font-weight: 500;'>Q{q_num} - Attempt {int(attempt_num)}</span>
                                            {''.join(step_badges)}
                                        </div>
                                        <span style='font-size: 12px; color: #666;'>{attempt_group['correct'].sum()} ✓ / {(~attempt_group['correct']).sum()} ✗</span>
                                    </div>
                                </div>
                                <div id='breakdown_{detail_id}' style='display: none; margin-left: 25px; margin-top: 5px;'>
                                    {''.join(step_details)}
                                </div>
                                <script>
                                    function toggleDetail_{detail_id}() {{
                                        var breakdown = document.getElementById('breakdown_{detail_id}');
                                        var arrow = document.getElementById('arrow_{detail_id}');
                                        if (breakdown.style.display === 'none') {{
                                            breakdown.style.display = 'block';
                                            arrow.style.transform = 'rotate(90deg)';
                                        }} else {{
                                            breakdown.style.display = 'none';
                                            arrow.style.transform = 'rotate(0deg)';
                                        }}
                                    }}
                                </script>
                            </div>
                            """)
                
                chart_bars.append(f"""
                <div style='margin: 8px 0;'>
                    <div style='display: flex; align-items: center; padding: 8px; background: #f8f9fa; border-radius: 6px; cursor: pointer; user-select: none;' onclick='toggleSection{idx}()'>
                        <span id='sectionArrow{idx}' style='display: inline-block; transition: transform 0.2s; margin-right: 8px;'>▶</span>
                        <div style='flex: 1;'>
                            <span style='display: inline-block; width: 12px; height: 12px; background: {color}; border-radius: 50%; margin-right: 8px;'></span>
                            <strong>{section_name}</strong>
                        </div>
                        <div style='margin-left: 10px; text-align: right;'>
                            <span style='color: #28a745; font-weight: 600;'>{int(row['correct'])} ✓</span> / 
                            <span style='color: #dc3545; font-weight: 600;'>{int(row['incorrect'])} ✗</span>
                            <span style='margin-left: 10px; font-weight: 600;'>({row['percentage']}%)</span>
                        </div>
                    </div>
                    <div id='sectionBreakdown{idx}' style='display: none; margin-top: 5px; margin-left: 15px;'>
                        {''.join(question_rows)}
                    </div>
                    <script>
                        function toggleSection{idx}() {{
                            var breakdown = document.getElementById('sectionBreakdown{idx}');
                            var arrow = document.getElementById('sectionArrow{idx}');
                            if (breakdown.style.display === 'none') {{
                                breakdown.style.display = 'block';
                                arrow.style.transform = 'rotate(90deg)';
                            }} else {{
                                breakdown.style.display = 'none';
                                arrow.style.transform = 'rotate(0deg)';
                            }}
                        }}
                    </script>
                </div>
                """)
            
            chart_html = f"""
            <div style='background: #ffffff; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #ddd;'>
                <h3 style='margin-bottom: 15px;'>Performance by Section</h3>
                {''.join(chart_bars)}
            </div>
            """
            
            # Overall statistics
            total_correct = all_attempts['correct'].sum()
            total_attempts = len(all_attempts)
            overall_pct = (total_correct / total_attempts * 100).round(1) if total_attempts > 0 else 0
            
            # Calculate question type statistics
            question_df = df()
            type_stats_rows = []
            
            # Create a mapping of (section, question_number, step) to question_type and question text
            # For each question, sub_questions are ordered, so step 1 = first sub_question, etc.
            step_to_type = {}
            step_to_question = {}
            for (section, question), group in question_df.groupby(['section', 'question_number']):
                sub_questions = group['sub_question'].unique()
                for step_idx, sub_q in enumerate(sub_questions, start=1):
                    sub_q_data = group[group['sub_question'] == sub_q]
                    if not sub_q_data.empty:
                        q_type = sub_q_data.iloc[0].get('question_type', 'Unknown')
                        step_to_type[(section, question, step_idx)] = q_type
                        step_to_question[(section, question, step_idx)] = sub_q
            
            # Add question_type and question text to all_attempts based on step number
            all_attempts['question_type'] = all_attempts.apply(
                lambda row: step_to_type.get((row['section'], row['question_number'], row['step']), 'Unknown'),
                axis=1
            )
            all_attempts['question_text'] = all_attempts.apply(
                lambda row: step_to_question.get((row['section'], row['question_number'], row['step']), ''),
                axis=1
            )
            
            all_attempts_with_types = all_attempts
            
            # Build performance table HTML with card-based design (after question_type is added)
            table_rows = []
            
            # Color mapping for question types (matching the type stats)
            type_colors = {
                'Formula Selection': '#007bff',
                'Algebraic Manipulation': '#fd7e14',
                'Substitute & Calculate': '#17a2b8',
                'Derivative': '#e83e8c',
                'Integral': '#6610f2',
                'Vector Components': '#20c997',
                'Force Calculation': '#dc3545',
                'Angle Calculation': '#28a745',
                'Kinematics Calculation': '#ffc107',
                'Final Answer': '#28a745',
            }
            
            for _, row in all_attempts_with_types.iterrows():
                bg_color = "#d4edda" if row['correct'] else "#f8d7da"
                icon_color = "#28a745" if row['correct'] else "#dc3545"
                icon = "✓" if row['correct'] else "✗"
                result_text = "Correct" if row['correct'] else "Incorrect"
                
                # Extract answer from details
                answer = ""
                if row['action'] == 'option_selected':
                    # Format: "Q: ... | A: ... | correct="
                    if 'A: ' in row['details']:
                        answer_part = row['details'].split('A: ')[1]
                        answer = answer_part.split(' | correct=')[0] if ' | correct=' in answer_part else answer_part
                elif row['action'] == 'answer_submitted':
                    # Format: "answer=X units, correct="
                    if 'answer=' in row['details']:
                        answer_part = row['details'].split('answer=')[1]
                        answer = answer_part.split(', correct=')[0] if ', correct=' in answer_part else answer_part
                
                # Get question type and text
                question_type = row.get('question_type', 'Unknown')
                question_text = row.get('question_text', '')
                type_color = type_colors.get(question_type, '#6c757d')
                
                # Determine step label
                step_label = f"Step {row['step']}" if row['action'] == 'option_selected' else "Final Answer"
                
                table_rows.append(f"""
                <div style='background: {bg_color}; padding: 12px 15px; margin: 5px 0; border-radius: 4px; border-left: 4px solid {icon_color};'>
                    <div style='display: flex; justify-content: space-between; align-items: flex-start; gap: 15px;'>
                        <div style='flex: 1;'>
                            <div style='display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px;'>
                                <strong style='font-size: 1.05em;'>{row['section']}</strong>
                                <span style='color: #555;'>Q{row['question_number']} • {step_label}</span>
                                <span style='background: {type_color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 500;'>{question_type}</span>
                            </div>
                            <div class='analytics-step-detail' style='margin: 8px 0; padding: 8px; background: rgba(255,255,255,0.7); border-radius: 3px; font-size: 0.95em; color: #333;'>{question_text}</div>
                            <div style='margin: 8px 0;'>
                                <strong style='font-size: 0.9em; color: #555;'>Your Answer:</strong>
                                <div class='analytics-answer-cell' style='margin-top: 4px; padding: 8px; background: white; border-radius: 3px; font-size: 0.95em;'>{answer}</div>
                            </div>
                        </div>
                        <div style='text-align: center; min-width: 70px;'>
                            <div style='color: {icon_color}; font-weight: 600; font-size: 20px;'>{icon}</div>
                            <div style='color: {icon_color}; font-size: 0.85em; font-weight: 500; margin-top: 4px;'>{result_text}</div>
                        </div>
                    </div>
                </div>
                """)
            
            table_html = f"""
            <div style='background: #ffffff; padding: 20px; border-radius: 8px; margin: 0 0 20px 0; border: 1px solid #ddd;'>
                <h3 style='margin-top: 0; margin-bottom: 15px;'>Detailed Results</h3>
                <div>
                    {''.join(table_rows)}
                </div>
            </div>
            """
            
            # Group by question type
            if 'question_type' in all_attempts_with_types.columns:
                type_stats = all_attempts_with_types.groupby('question_type')['correct'].agg(['sum', 'count']).reset_index()
                type_stats.columns = ['question_type', 'correct', 'total']
                type_stats['percentage'] = (type_stats['correct'] / type_stats['total'] * 100).round(1)
                type_stats = type_stats.sort_values('percentage', ascending=False)
                
                # Color mapping for 10 question types
                type_colors = {
                    'Formula Selection': '#007bff',
                    'Algebraic Manipulation': '#fd7e14',
                    'Substitute & Calculate': '#17a2b8',
                    'Derivative': '#e83e8c',
                    'Integral': '#6610f2',
                    'Vector Components': '#20c997',
                    'Force Calculation': '#dc3545',
                    'Angle Calculation': '#28a745',
                    'Kinematics Calculation': '#ffc107',
                    'Final Answer': '#28a745',
                }
                
                for type_idx, row in type_stats.iterrows():
                    qtype = row['question_type']
                    color = type_colors.get(qtype, '#6c757d')
                    
                    # Get detailed breakdown for this question type
                    type_attempts = all_attempts_with_types[all_attempts_with_types['question_type'] == qtype]
                    detail_rows = []
                    
                    # Group by section, question, and attempt
                    detail_counter = 0
                    for (section, question), q_group in type_attempts.groupby(['section', 'question_number']):
                        for attempt_num, attempt_group in q_group.groupby('attempt_num'):
                            detail_counter += 1
                            detail_id = f"type{type_idx}_detail{detail_counter}"
                            
                            step_badges = []
                            step_details = []
                            
                            for _, attempt_row in attempt_group.iterrows():
                                step_bg = '#28a745' if attempt_row['correct'] else '#dc3545'
                                if attempt_row['action'] == 'answer_submitted':
                                    step_label = 'T' if attempt_row['correct'] else 'F'
                                    step_type = 'Final Answer'
                                else:
                                    step_label = str(int(attempt_row['step']))
                                    step_type = f"Step {int(attempt_row['step'])}"
                                
                                step_badges.append(f"<span style='display: inline-block; background: {step_bg}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; margin-left: 6px; font-weight: 600; min-width: 28px; text-align: center;'>{step_label}</span>")
                                
                                # Extract question and answer from details
                                details_str = attempt_row['details']
                                question_text = ""
                                answer_text = ""
                                
                                if attempt_row['action'] == 'option_selected':
                                    # Format: "Q: ... | A: ... | correct=..."
                                    if 'Q: ' in details_str and 'A: ' in details_str:
                                        q_part = details_str.split('Q: ')[1].split(' | A: ')[0] if ' | A: ' in details_str else ""
                                        a_part = details_str.split('A: ')[1].split(' | correct=')[0] if ' | correct=' in details_str else details_str.split('A: ')[1]
                                        question_text = q_part
                                        answer_text = a_part
                                elif attempt_row['action'] == 'answer_submitted':
                                    # Format: "answer=X units, correct=..."
                                    if 'answer=' in details_str:
                                        answer_text = details_str.split('answer=')[1].split(', correct=')[0] if ', correct=' in details_str else details_str.split('answer=')[1]
                                        question_text = "Final numerical answer"
                                
                                result_icon = "✓" if attempt_row['correct'] else "✗"
                                result_color = "#28a745" if attempt_row['correct'] else "#dc3545"
                                
                                step_details.append(f"""
                                <div style='padding: 10px; margin: 5px 0; background: white; border-radius: 4px; border-left: 3px solid {step_bg};'>
                                    <div style='font-weight: 600; color: {step_bg}; margin-bottom: 5px;'>{step_type} <span style='color: {result_color}; margin-left: 8px;'>{result_icon}</span></div>
                                    {f"<div style='margin: 5px 0; color: #666; font-size: 0.95em;'><strong>Question:</strong> <span class='analytics-step-detail'>{question_text}</span></div>" if question_text else ""}
                                    <div style='margin: 5px 0; color: #333;'><strong>Answer:</strong> <span class='analytics-step-detail'>{answer_text}</span></div>
                                </div>
                                """)
                            
                            detail_rows.append(f"""
                            <div style='margin: 5px 0;'>
                                <div style='padding: 8px 15px; border-left: 3px solid {color}; background: #f9f9f9; border-radius: 4px; cursor: pointer; user-select: none;' onclick='toggleDetail_{detail_id}()'>
                                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                                        <div>
                                            <span id='arrow_{detail_id}' style='display: inline-block; transition: transform 0.2s; margin-right: 8px;'>▶</span>
                                            <span style='font-weight: 500;'>{section} - Q{question} - Attempt {int(attempt_num)}</span>
                                            {''.join(step_badges)}
                                        </div>
                                        <span style='font-size: 12px; color: #666;'>{attempt_group['correct'].sum()} ✓ / {(~attempt_group['correct']).sum()} ✗</span>
                                    </div>
                                </div>
                                <div id='breakdown_{detail_id}' style='display: none; margin-left: 25px; margin-top: 5px;'>
                                    {''.join(step_details)}
                                </div>
                                <script>
                                    function toggleDetail_{detail_id}() {{
                                        var breakdown = document.getElementById('breakdown_{detail_id}');
                                        var arrow = document.getElementById('arrow_{detail_id}');
                                        if (breakdown.style.display === 'none') {{
                                            breakdown.style.display = 'block';
                                            arrow.style.transform = 'rotate(90deg)';
                                        }} else {{
                                            breakdown.style.display = 'none';
                                            arrow.style.transform = 'rotate(0deg)';
                                        }}
                                    }}
                                </script>
                            </div>
                            """)
                    
                    type_stats_rows.append(f"""
                    <div style='margin: 8px 0;'>
                        <div style='display: flex; align-items: center; padding: 8px; background: #f8f9fa; border-radius: 6px; cursor: pointer; user-select: none;' onclick='toggleType{type_idx}()'>
                            <span id='typeArrow{type_idx}' style='display: inline-block; transition: transform 0.2s; margin-right: 8px;'>▶</span>
                            <div style='flex: 1;'>
                                <span style='display: inline-block; width: 12px; height: 12px; background: {color}; border-radius: 50%; margin-right: 8px;'></span>
                                <strong>{qtype}</strong>
                            </div>
                            <div style='margin-left: 10px; text-align: right;'>
                                <span style='color: #28a745; font-weight: 600;'>{int(row['correct'])} ✓</span> / 
                                <span style='color: #dc3545; font-weight: 600;'>{int(row['total'] - row['correct'])} ✗</span>
                                <span style='margin-left: 10px; font-weight: 600;'>({row['percentage']}%)</span>
                            </div>
                        </div>
                        <div id='typeBreakdown{type_idx}' style='display: none; margin-top: 5px; margin-left: 15px;'>
                            {''.join(detail_rows)}
                        </div>
                        <script>
                            function toggleType{type_idx}() {{
                                var breakdown = document.getElementById('typeBreakdown{type_idx}');
                                var arrow = document.getElementById('typeArrow{type_idx}');
                                if (breakdown.style.display === 'none') {{
                                    breakdown.style.display = 'block';
                                    arrow.style.transform = 'rotate(90deg)';
                                }} else {{
                                    breakdown.style.display = 'none';
                                    arrow.style.transform = 'rotate(0deg)';
                                }}
                            }}
                        </script>
                    </div>
                    """)
            
            type_stats_html = f"""
            <div style='background: #ffffff; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #ddd;'>
                <h3 style='margin-bottom: 15px;'>Performance by Question Type</h3>
                {''.join(type_stats_rows) if type_stats_rows else '<p style="color: #666;">No question type data available</p>'}
            </div>
            """ if type_stats_rows else ""
            
            stats_html = f"""
            <div style='background: #ffffff; padding: 25px; border-radius: 8px; margin: 0 0 20px 0; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                <h3 style='color: #333; margin-bottom: 20px;'>Overall Statistics</h3>
                <div style='display: flex; gap: 15px; flex-wrap: wrap; align-items: stretch;'>
                    <div style='flex: 1; min-width: 150px; text-align: center; padding: 15px; background: #f8f9fa; border-radius: 6px; border: 1px solid #dee2e6; display: flex; flex-direction: column; justify-content: center;'>
                        <div style='font-size: 48px; font-weight: bold; margin-bottom: 5px; color: #333;'>{overall_pct}%</div>
                        <div style='font-size: 14px; color: #666;'>Success Rate</div>
                    </div>
                    <div style='flex: 1; min-width: 150px; background: #d4edda; padding: 15px; border-radius: 6px; border: 1px solid #c3e6cb; display: flex; flex-direction: column; justify-content: center;'>
                        <div style='font-size: 32px; font-weight: bold; color: #28a745;'>{total_correct}</div>
                        <div style='font-size: 14px; color: #155724;'>✓ Correct</div>
                    </div>
                    <div style='flex: 1; min-width: 150px; background: #f8d7da; padding: 15px; border-radius: 6px; border: 1px solid #f5c6cb; display: flex; flex-direction: column; justify-content: center;'>
                        <div style='font-size: 32px; font-weight: bold; color: #dc3545;'>{total_attempts - total_correct}</div>
                        <div style='font-size: 14px; color: #721c24;'>✗ Incorrect</div>
                    </div>
                </div>
            </div>
            """
            
            return ui.div(
                ui.HTML(stats_html),
                ui.HTML(type_stats_html) if type_stats_rows else ui.div(),
                ui.HTML(chart_html),
                ui.HTML(table_html),
                ui.tags.script(r"""
                    function renderAllMath() {
                        setTimeout(function() {
                            try {
                                const cells = document.querySelectorAll('.analytics-answer-cell, .analytics-step-detail');
                                cells.forEach(function(cell) {
                                    // Only render if not already rendered
                                    if (!cell.classList.contains('katex-rendered')) {
                                        try {
                                            // Convert display math to inline for single-line flow
                                            let content = cell.innerHTML;
                                            content = content.replace(/\$\$/g, '$');
                                            cell.innerHTML = content;
                                            
                                            renderMathInElement(cell, {
                                                delimiters: [
                                                    {left: "$$", right: "$$", display: true},
                                                    {left: "$", right: "$", display: false}
                                                ],
                                                throwOnError: false
                                            });
                                            cell.classList.add('katex-rendered');
                                        } catch (e) {
                                            console.log('Math rendering skipped for cell:', e);
                                        }
                                    }
                                });
                            } catch (error) {
                                console.error('Error rendering math in analytics:', error);
                            }
                        }, 100);
                    }
                    
                    // Initial render
                    if (document.readyState === 'loading') {
                        document.addEventListener('DOMContentLoaded', renderAllMath);
                    } else {
                        renderAllMath();
                    }
                    
                    // Single delayed render for dynamic content
                    setTimeout(renderAllMath, 500);
                    
                    // Add click listener - render math after clicks on drill-downs
                    document.addEventListener('click', function(e) {
                        // Only render if clicking on elements with onclick (drill-down toggles)
                        if (e.target.closest('[onclick]') || e.target.closest('[id*="Arrow"]') || e.target.closest('[id*="type"]')) {
                            requestAnimationFrame(function() {
                                setTimeout(renderAllMath, 200);
                            });
                        }
                    });
                """),
                style="padding: 20px;"
            )
            
        except Exception as e:
            return ui.div(
                ui.h2("Error Loading Analytics"),
                ui.p(f"Could not parse performance data: {str(e)}"),
                style="text-align: center; padding: 50px;"
            )

    @render.download(filename="data.csv")
    def download_data():
        csv = csv_data()
        if not csv.strip():
            csv = "user_id,timestamp,section,question_number,step,action,details\n"
        import io
        return io.BytesIO(csv.encode('utf-8-sig'))

    @render.download(filename=lambda: f"session_{session.id}.csv")
    def download_my_session():
        import io
        if csv_data().strip():
            try:
                # Clean and parse the CSV data
                content = csv_data()
                content = content.replace('\r\n', '\n').replace('\r', '\n')
                df_data = pd.read_csv(io.StringIO(content), engine='python')
                # Filter for just this user's data
                user_data = df_data[df_data['user_id'] == session.id]
                # Convert back to CSV
                csv_output = user_data.to_csv(index=False)
                return io.BytesIO(csv_output.encode('utf-8-sig'))
            except Exception as e:
                # If parsing fails, return empty CSV with headers
                csv = "user_id,timestamp,section,question_number,step,action,details\n"
                return io.BytesIO(csv.encode('utf-8-sig'))
        else:
            # Return empty CSV with headers
            csv = "user_id,timestamp,section,question_number,step,action,details\n"
            return io.BytesIO(csv.encode('utf-8-sig'))

# point Shiny at your www/ folder so anything under www/ is served at /
www_path = Path(__file__).parent / "www"
app = App(app_ui, server, static_assets=www_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
