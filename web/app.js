// EPL Forecast Web App
const API_ENDPOINT = 'https://aiighxj72l.execute-api.us-west-2.amazonaws.com/prod/table';

// Team logo mapping (using crests.football-data.org)
const TEAM_LOGOS = {
    'Arsenal FC': 'https://crests.football-data.org/57.png',
    'Aston Villa FC': 'https://crests.football-data.org/58.png',
    'AFC Bournemouth': 'https://crests.football-data.org/1044.png',
    'Brentford FC': 'https://crests.football-data.org/402.png',
    'Brighton & Hove Albion FC': 'https://crests.football-data.org/397.png',
    'Chelsea FC': 'https://crests.football-data.org/61.png',
    'Crystal Palace FC': 'https://crests.football-data.org/354.png',
    'Everton FC': 'https://crests.football-data.org/62.png',
    'Fulham FC': 'https://crests.football-data.org/63.png',
    'Ipswich Town FC': 'https://crests.football-data.org/349.png',
    'Leicester City FC': 'https://crests.football-data.org/338.png',
    'Liverpool FC': 'https://crests.football-data.org/64.png',
    'Manchester City FC': 'https://crests.football-data.org/65.png',
    'Manchester United FC': 'https://crests.football-data.org/66.png',
    'Newcastle United FC': 'https://crests.football-data.org/67.png',
    'Nottingham Forest FC': 'https://crests.football-data.org/351.png',
    'Southampton FC': 'https://crests.football-data.org/340.png',
    'Tottenham Hotspur FC': 'https://crests.football-data.org/73.png',
    'West Ham United FC': 'https://crests.football-data.org/563.png',
    'Wolverhampton Wanderers FC': 'https://crests.football-data.org/76.png'
};

// DOM elements
const refreshBtn = document.getElementById('refreshBtn');
const lastUpdatedEl = document.getElementById('lastUpdated');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const tableContainer = document.getElementById('tableContainer');
const tableBody = document.getElementById('tableBody');

// State
let currentData = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadForecastData();
    refreshBtn.addEventListener('click', () => {
        loadForecastData(true);
    });
});

// Load forecast data from API
async function loadForecastData(isManualRefresh = false) {
    try {
        // Show loading state
        if (isManualRefresh) {
            refreshBtn.classList.add('loading');
            refreshBtn.disabled = true;
        } else {
            showLoading();
        }

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
    } finally {
        refreshBtn.classList.remove('loading');
        refreshBtn.disabled = false;
    }
}

// Render the forecast table
function renderTable(teams, metadata) {
    tableBody.innerHTML = '';

    teams.forEach((team) => {
        const row = document.createElement('tr');

        // Calculate position change
        const currentPos = team.current_position;
        const forecastPos = team.forecasted_position;
        const posChange = currentPos - forecastPos;

        let changeIndicator = '';
        let changeClass = '';
        let changeText = '';

        if (posChange > 0) {
            changeIndicator = '▲';
            changeClass = 'up';
            changeText = `+${posChange}`;
        } else if (posChange < 0) {
            changeIndicator = '▼';
            changeClass = 'down';
            changeText = `${posChange}`;
        } else {
            changeIndicator = '–';
            changeClass = 'same';
            changeText = '0';
        }

        const logoUrl = TEAM_LOGOS[team.name] || '';

        row.innerHTML = `
            <td class="col-position">${forecastPos}</td>
            <td class="col-team">
                <div class="team-info">
                    ${logoUrl ? `<img src="${logoUrl}" alt="${escapeHtml(team.name)}" class="team-logo" onerror="this.style.display='none'">` : ''}
                    <span class="team-name">${escapeHtml(team.name)}</span>
                </div>
            </td>
            <td class="col-stat">${team.played}</td>
            <td class="col-stat">${team.points}</td>
            <td class="col-stat">${formatDecimal(team.points_per_game)}</td>
            <td class="col-stat">${team.goal_difference >= 0 ? '+' : ''}${team.goal_difference}</td>
            <td class="col-forecast">
                <span class="forecast-position">${formatDecimal(team.forecasted_points)}</span>
            </td>
            <td class="col-change">
                <span class="change-indicator ${changeClass}">${changeIndicator}</span>
                <span class="change-value">${changeText}</span>
            </td>
        `;

        tableBody.appendChild(row);
    });

    tableContainer.style.display = 'block';
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
