# Dark Theme + Glassmorphism Premium Stylesheet
# Colors: 
# Background: Deep Navy (#0a0f1e) 
# Sidebar Background: Dark Purple (#1a0533)
# Base Text: White (#ffffff)
# Accent 1: Cyan (#00f5d4)
# Accent 2: Purple (#7b61ff)

MAIN_STYLESHEET = """
QMainWindow {
    background-color: #0a0f1e;
}

QWidget {
    color: #ffffff;
    font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
}

/* Sidebar styling */
#Sidebar {
    background-color: #1a0533;
    border-right: 1px solid rgba(123, 97, 255, 0.3);
}

#Sidebar QPushButton {
    background-color: transparent;
    color: #ffffff;
    font-size: 16px;
    font-weight: 500;
    text-align: left;
    padding: 12px 20px;
    border: none;
    border-left: 4px solid transparent;
}

#Sidebar QPushButton:hover {
    background-color: rgba(123, 97, 255, 0.1);
}

#Sidebar QPushButton:checked {
    background-color: rgba(0, 245, 212, 0.1);
    color: #00f5d4;
    border-left: 4px solid #00f5d4;
    font-weight: bold;
}

/* Glassmorphism Cards */
.GlassCard {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}

.GlassCard:hover {
    border: 1px solid rgba(0, 245, 212, 0.4);
    background-color: rgba(0, 245, 212, 0.05);
}

/* Titles and Texts */
.TitleText {
    font-size: 24px;
    font-weight: bold;
    color: #ffffff;
}

.SubtitleText {
    font-size: 16px;
    color: #a0aabf;
}

.HighlightCyan {
    color: #00f5d4;
    font-weight: bold;
}

.HighlightPurple {
    color: #7b61ff;
    font-weight: bold;
}

/* Call to Action Buttons */
.CTAButton {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, 
                                      stop: 0 #7b61ff, stop: 1 #00f5d4);
    color: #0a0f1e;
    font-size: 16px;
    font-weight: bold;
    padding: 10px 20px;
    border-radius: 20px;
    border: none;
}

.CTAButton:hover {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, 
                                      stop: 0 #8b75ff, stop: 1 #33ffdf);
}

.CTAButton:pressed {
    background-color: #00f5d4;
}

.CTAButton_Secondary {
    background-color: transparent;
    color: #00f5d4;
    font-size: 16px;
    font-weight: bold;
    padding: 10px 20px;
    border-radius: 20px;
    border: 2px solid #00f5d4;
}

.CTAButton_Secondary:hover {
    background-color: rgba(0, 245, 212, 0.1);
}

/* Labels */
.WarningText {
    color: #ff4d4f;
    font-weight: bold;
}

.SuccessText {
    color: #00f5d4;
    font-weight: bold;
}

QProgressBar {
    background-color: #1a0533;
    border: 1px solid rgba(123, 97, 255, 0.3);
    border-radius: 5px;
    text-align: center;
    color: white;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, 
                                      stop: 0 #7b61ff, stop: 1 #00f5d4);
    border-radius: 4px;
}
"""
