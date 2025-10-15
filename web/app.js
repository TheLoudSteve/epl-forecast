// EPL Forecast Web App
const API_ENDPOINT = 'https://aiighxj72l.execute-api.us-west-2.amazonaws.com/prod/table';

// Team logo mapping (using crests.football-data.org)
const TEAM_LOGOS = {
    'Arsenal FC': 'https://crests.football-data.org/57.png',
    'Aston Villa FC': 'https://crests.football-data.org/58.png',
    'AFC Bournemouth': 'https://crests.football-data.org/1044.png',
    'Brentford FC': 'https://crests.football-data.org/402.png',
    'Brighton & Hove Albion FC': 'https://crests.football-data.org/397.png',
    'Burnley FC': 'https://crests.football-data.org/328.png',
    'Chelsea FC': 'https://crests.football-data.org/61.png',
    'Crystal Palace FC': 'https://crests.football-data.org/354.png',
    'Everton FC': 'https://crests.football-data.org/62.png',
    'Fulham FC': 'https://crests.football-data.org/63.png',
    'Ipswich Town FC': 'https://crests.football-data.org/349.png',
    'Leeds United FC': 'https://crests.football-data.org/341.png',
    'Leicester City FC': 'https://crests.football-data.org/338.png',
    'Liverpool FC': 'https://crests.football-data.org/64.png',
    'Manchester City FC': 'https://crests.football-data.org/65.png',
    'Manchester United FC': 'https://crests.football-data.org/66.png',
    'Newcastle United FC': 'https://crests.football-data.org/67.png',
    'Nottingham Forest FC': 'https://crests.football-data.org/351.png',
    'Southampton FC': 'https://crests.football-data.org/340.png',
    'Sunderland AFC': 'https://crests.football-data.org/71.png',
    'Tottenham Hotspur FC': 'https://crests.football-data.org/73.png',
    'West Ham United FC': 'https://crests.football-data.org/563.png',
    'Wolverhampton Wanderers FC': 'https://crests.football-data.org/76.png'
};

// DOM elements
const lastUpdatedEl = document.getElementById('lastUpdated');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const tableContainer = document.getElementById('tableContainer');
const tableBody = document.getElementById('tableBody');
const forecastBtn = document.getElementById('forecastBtn');
const liveBtn = document.getElementById('liveBtn');
const favoriteTeamSelect = document.getElementById('favoriteTeam');
const hamburgerBtn = document.getElementById('hamburgerBtn');
const favoriteTeamSelector = document.getElementById('favoriteTeamSelector');

// State
let currentData = null;
let currentView = 'forecast'; // 'forecast' or 'live'
let favoriteTeam = localStorage.getItem('favoriteTeam') || '';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadForecastData();

    // Show hamburger if favorite team is already set
    if (favoriteTeam) {
        favoriteTeamSelector.style.display = 'none';
        hamburgerBtn.style.display = 'block';
    }

    // Toggle button listeners
    forecastBtn.addEventListener('click', () => {
        if (currentView !== 'forecast') {
            currentView = 'forecast';
            forecastBtn.classList.add('active');
            liveBtn.classList.remove('active');
            if (currentData) {
                renderTable(currentData.forecast_table, currentData.metadata);
            }
        }
    });

    liveBtn.addEventListener('click', () => {
        if (currentView !== 'live') {
            currentView = 'live';
            liveBtn.classList.add('active');
            forecastBtn.classList.remove('active');
            if (currentData) {
                renderTable(currentData.forecast_table, currentData.metadata);
            }
        }
    });

    // Hamburger menu toggle
    hamburgerBtn.addEventListener('click', () => {
        if (favoriteTeamSelector.style.display === 'none') {
            favoriteTeamSelector.style.display = 'flex';
            hamburgerBtn.style.display = 'none';
        }
    });

    // Favorite team selector
    favoriteTeamSelect.addEventListener('change', (e) => {
        favoriteTeam = e.target.value;
        if (favoriteTeam) {
            localStorage.setItem('favoriteTeam', favoriteTeam);
            // Hide selector, show hamburger
            favoriteTeamSelector.style.display = 'none';
            hamburgerBtn.style.display = 'block';
        } else {
            localStorage.removeItem('favoriteTeam');
        }
        if (currentData) {
            renderTable(currentData.forecast_table, currentData.metadata);
        }
    });
});

// Load forecast data from API
async function loadForecastData() {
    try {
        showLoading();

        // Fetch data
        const response = await fetch(API_ENDPOINT);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Validate data structure - API uses 'forecast_table' not 'teams'
        if (!data.forecast_table || !Array.isArray(data.forecast_table)) {
            console.error('API Response:', data);
            console.error('Has forecast_table:', 'forecast_table' in data);
            console.error('forecast_table type:', typeof data.forecast_table);
            throw new Error(`Invalid data format received from API. Keys: ${Object.keys(data).join(', ')}`);
        }

        currentData = data;
        renderTable(data.forecast_table, data.metadata);
        updateLastUpdated(data.metadata?.last_updated);
        hideLoading();
        hideError();

    } catch (error) {
        console.error('Error loading forecast data:', error);
        showError(`Failed to load forecast data: ${error.message}`);
        hideLoading();
    }
}

// Render the forecast table
function renderTable(teams, metadata) {
    tableBody.innerHTML = '';

    // Populate team dropdown if empty
    if (favoriteTeamSelect.options.length === 1) {
        const sortedTeamNames = [...teams]
            .map(t => t.name)
            .sort();

        sortedTeamNames.forEach(teamName => {
            const option = document.createElement('option');
            option.value = teamName;
            option.textContent = teamName;
            if (teamName === favoriteTeam) {
                option.selected = true;
            }
            favoriteTeamSelect.appendChild(option);
        });
    }

    // Sort teams based on current view
    let sortedTeams;
    if (currentView === 'live') {
        // Sort by current position
        sortedTeams = [...teams].sort((a, b) => a.current_position - b.current_position);
    } else {
        // Sort by forecasted position
        sortedTeams = [...teams].sort((a, b) => a.forecasted_position - b.forecasted_position);
    }

    sortedTeams.forEach((team) => {
        const row = document.createElement('tr');

        // Mark favorite team
        const isFavorite = team.name === favoriteTeam;
        if (isFavorite) {
            row.classList.add('favorite-team');
            row.id = 'favorite-team-row';
        }

        const logoUrl = TEAM_LOGOS[team.name] || '';

        // Determine which position and points to display
        const displayPosition = currentView === 'live' ? team.current_position : team.forecasted_position;
        const displayPoints = currentView === 'live' ? team.points : Math.round(team.forecasted_points);
        const pointsLabel = currentView === 'live' ? 'pts' : 'proj';

        // Determine position-based color class
        let positionClass = 'position-mid-table';
        if (displayPosition <= 4) {
            positionClass = 'position-champions-league';
        } else if (displayPosition >= 18) {
            positionClass = 'position-relegation';
        }

        row.innerHTML = `
            <td class="col-team">
                <div class="team-info">
                    <div class="team-content">
                        <span class="position-indicator ${positionClass}">${displayPosition}</span>
                        ${logoUrl ? `<img src="${logoUrl}" alt="${escapeHtml(team.name)}" class="team-logo" onerror="this.style.display='none'">` : ''}
                        <div class="team-details">
                            <span class="team-name">${escapeHtml(team.name)}</span>
                            <span class="team-stats">${team.played} GP | ${team.points} PTS | ${formatDecimal(team.points_per_game)} PPG</span>
                        </div>
                    </div>
                </div>
            </td>
            <td class="col-forecast">
                <div class="forecast-points">
                    <span class="forecast-points-value ${isFavorite ? positionClass : ''}">${displayPoints}</span>
                    <span class="forecast-points-label">${pointsLabel}</span>
                </div>
            </td>
        `;

        tableBody.appendChild(row);
    });

    tableContainer.style.display = 'block';

    // Scroll to favorite team if set
    if (favoriteTeam) {
        setTimeout(() => {
            const favoriteRow = document.getElementById('favorite-team-row');
            if (favoriteRow) {
                favoriteRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }, 100);
    }
}

// Update last updated timestamp
function updateLastUpdated(timestamp) {
    if (!timestamp) return;

    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        let timeAgo = '';
        if (diffDays > 0) {
            timeAgo = `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        } else if (diffHours > 0) {
            timeAgo = `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        } else if (diffMins > 0) {
            timeAgo = `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
        } else {
            timeAgo = 'Just now';
        }

        lastUpdatedEl.textContent = `Last updated: ${timeAgo}`;
    } catch (error) {
        lastUpdatedEl.textContent = 'Last updated: Unknown';
    }
}

// UI state management
function showLoading() {
    loadingEl.style.display = 'block';
    tableContainer.style.display = 'none';
    errorEl.style.display = 'none';
}

function hideLoading() {
    loadingEl.style.display = 'none';
}

function showError(message) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    tableContainer.style.display = 'none';
}

function hideError() {
    errorEl.style.display = 'none';
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDecimal(value) {
    if (typeof value === 'number') {
        return value.toFixed(1);
    }
    // Handle Decimal string format from Python
    return parseFloat(value).toFixed(1);
}

// Auto-refresh every 5 minutes
setInterval(() => {
    if (document.visibilityState === 'visible') {
        loadForecastData();
    }
}, 5 * 60 * 1000);

// Refresh when tab becomes visible
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && currentData) {
        const lastUpdate = new Date(currentData.last_updated);
        const now = new Date();
        const diffMins = Math.floor((now - lastUpdate) / 60000);

        // Refresh if data is older than 5 minutes
        if (diffMins > 5) {
            loadForecastData();
        }
    }
});
