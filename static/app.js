document.addEventListener("DOMContentLoaded", () => {
  // Global Application State
  const state = {
    user: null,
    reviewsPage: 1,
    reviewsFilter: { sentiment: "all", rating: "all", search: "" },
    expandedStudentId: null,
    adminSearchQuery: "",
    charts: {},
    hotelSearchTimeout: null
  };

  // --- INITIALIZATION ---
  checkAuth();
  fetchSummaryData();
  fetchThemes();
  fetchReviews(1);
  setupSandboxListeners();
  setupAdminSearchListener();

  // --- AUTH & ROLE MANAGEMENT ---
  async function checkAuth() {
    try {
      const res = await fetch("/api/auth/me");
      const data = await res.json();
      updateUserUI(data);
    } catch (e) {
      console.error("Auth check error:", e);
    }
  }

  function updateUserUI(user) {
    state.user = user;
    const statusContainer = document.getElementById("userStatusContainer");
    const loginBtn = document.getElementById("loginNavBtn");
    const adminSection = document.getElementById("adminSection");
    const logoutSection = document.getElementById("logoutSection");
    const studentReviewCard = document.getElementById("studentReviewCard");

    const isAuthenticated = user && (user.authenticated === true || (user.id && user.role !== "guest"));

    if (isAuthenticated) {
      loginBtn.innerText = "Account / Logout";
      logoutSection.style.display = "block";

      if (user.role === "student") {
        statusContainer.innerHTML = `
          <span class="user-status-pill status-student">
            🎓 Student: <strong>${escapeHtml(user.name)}</strong> (${escapeHtml(user.email)})
          </span>
        `;
        adminSection.style.display = "none";
        studentReviewCard.style.display = "block";
      } else if (user.role === "owner") {
        statusContainer.innerHTML = `
          <span class="user-status-pill status-owner">
            🏨 Owner: <strong>${escapeHtml(user.name)}</strong> (${escapeHtml(user.email)})
          </span>
        `;
        adminSection.style.display = "block";
        studentReviewCard.style.display = "block"; // Owner can also test review submission
        fetchAdminStudents();
      }
    } else {
      statusContainer.innerHTML = `
        <span class="user-status-pill status-guest">
          ⚪ Not Logged In — Click Login
        </span>
      `;
      loginBtn.innerText = "Log In / Sign Up";
      logoutSection.style.display = "none";
      adminSection.style.display = "none";
      studentReviewCard.style.display = "none";
    }
  }

  window.openAuthModal = () => {
    hideAuthAlerts();
    document.getElementById("authModal").classList.add("active");
  };

  window.closeAuthModal = () => {
    document.getElementById("authModal").classList.remove("active");
  };

  window.switchAuthTab = (tab) => {
    hideAuthAlerts();
    const loginForm = document.getElementById("loginForm");
    const signupForm = document.getElementById("signupForm");
    const forgotForm = document.getElementById("forgotForm");
    const resetForm = document.getElementById("resetForm");

    const tabLoginBtn = document.getElementById("tabLoginBtn");
    const tabSignupBtn = document.getElementById("tabSignupBtn");
    const tabForgotBtn = document.getElementById("tabForgotBtn");

    loginForm.style.display = "none";
    signupForm.style.display = "none";
    forgotForm.style.display = "none";
    resetForm.style.display = "none";

    tabLoginBtn.style.borderBottom = "none";
    tabLoginBtn.style.color = "var(--text-dim)";
    tabSignupBtn.style.borderBottom = "none";
    tabSignupBtn.style.color = "var(--text-dim)";
    tabForgotBtn.style.borderBottom = "none";
    tabForgotBtn.style.color = "var(--text-dim)";

    if (tab === "login") {
      loginForm.style.display = "block";
      tabLoginBtn.style.borderBottom = "2px solid var(--accent-primary)";
      tabLoginBtn.style.color = "var(--text-main)";
    } else if (tab === "signup") {
      signupForm.style.display = "block";
      tabSignupBtn.style.borderBottom = "2px solid var(--accent-cyan)";
      tabSignupBtn.style.color = "var(--text-main)";
    } else if (tab === "forgot") {
      forgotForm.style.display = "block";
      tabForgotBtn.style.borderBottom = "2px solid var(--accent-amber)";
      tabForgotBtn.style.color = "var(--text-main)";
    }
  };

  window.fillQuickCreds = (email, password) => {
    switchAuthTab("login");
    document.getElementById("loginEmail").value = email;
    document.getElementById("loginPassword").value = password;
  };

  function showAuthError(msg) {
    const box = document.getElementById("authErrorAlert");
    box.innerText = msg;
    box.style.display = "block";
    document.getElementById("authSuccessAlert").style.display = "none";
  }

  function showAuthSuccess(msg) {
    const box = document.getElementById("authSuccessAlert");
    box.innerText = msg;
    box.style.display = "block";
    document.getElementById("authErrorAlert").style.display = "none";
  }

  function hideAuthAlerts() {
    document.getElementById("authErrorAlert").style.display = "none";
    document.getElementById("authSuccessAlert").style.display = "none";
  }

  window.handleLoginSubmit = async (e) => {
    e.preventDefault();
    hideAuthAlerts();

    const email = document.getElementById("loginEmail").value;
    const password = document.getElementById("loginPassword").value;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        updateUserUI(data.user);
        closeAuthModal();
      } else {
        showAuthError(data.message || "Login failed. Check your credentials.");
      }
    } catch (err) {
      showAuthError("Network error: " + err.message);
    }
  };

  window.handleSignupSubmit = async (e) => {
    e.preventDefault();
    hideAuthAlerts();

    const name = document.getElementById("signupName").value;
    const email = document.getElementById("signupEmail").value;
    const password = document.getElementById("signupPassword").value;

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        updateUserUI(data.user);
        closeAuthModal();
      } else {
        showAuthError(data.message || "Signup failed. Please try again.");
      }
    } catch (err) {
      showAuthError("Network error: " + err.message);
    }
  };

  // --- FORGOT & RESET PASSWORD HANDLERS ---
  window.handleForgotPasswordRequest = async (e) => {
    e.preventDefault();
    hideAuthAlerts();

    const identifier = document.getElementById("forgotEmail").value.trim();
    if (!identifier) return;

    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        showAuthSuccess(data.message);
        document.getElementById("forgotForm").style.display = "none";
        document.getElementById("resetForm").style.display = "block";
        document.getElementById("resetEmail").value = data.user_email || identifier;
        document.getElementById("resetCode").value = "";
      } else {
        showAuthError(data.message || "Failed to generate reset code.");
      }
    } catch (err) {
      showAuthError("Network error: " + err.message);
    }
  };

  window.handleResetPasswordSubmit = async (e) => {
    e.preventDefault();
    hideAuthAlerts();

    const identifier = document.getElementById("resetEmail").value.trim();
    const code = document.getElementById("resetCode").value.trim();
    const new_password = document.getElementById("resetNewPassword").value;

    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, code, new_password })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        showAuthSuccess("Password reset successfully! Switch to Log In tab.");
        setTimeout(() => {
          switchAuthTab("login");
          document.getElementById("loginEmail").value = identifier;
          document.getElementById("loginPassword").value = new_password;
        }, 1200);
      } else {
        showAuthError(data.message || "Password reset failed.");
      }
    } catch (err) {
      showAuthError("Network error: " + err.message);
    }
  };

  window.logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    checkAuth();
    closeAuthModal();
  };

  // --- STUDENT HOTEL REVIEW SUBMISSION ---
  // --- HOTEL SEARCH & AUTOCOMPLETE ---
  window.handleHotelSearch = async (query) => {
    const dropdown = document.getElementById("hotelAutocompleteDropdown");
    const infoBox = document.getElementById("hotelResultsInfo");

    if (!query || query.length < 1) {
      dropdown.style.display = "none";
      infoBox.innerText = "";
      return;
    }

    clearTimeout(state.hotelSearchTimeout);
    state.hotelSearchTimeout = setTimeout(async () => {
      try {
        const res = await fetch(`/api/hotels/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();

        if (res.ok && data.success && data.hotels.length > 0) {
          let html = "";
          for (const hotel of data.hotels) {
            html += `
              <div style="padding:0.75rem; border-bottom:1px solid var(--line); cursor:pointer;"
                   onmouseover="this.style.background='var(--card-hover)';"
                   onmouseout="this.style.background='transparent';"
                   onclick="selectHotel('${escapeHtml(hotel.name)}', '${escapeHtml(JSON.stringify(hotel))}')">
                <div style="font-weight:600; color:var(--orange);">🏨 🇮🇳 ${escapeHtml(hotel.name)}</div>
                <div style="font-size:0.8rem; color:var(--text-muted);">📍 ${escapeHtml(hotel.address)}</div>
                <div style="font-size:0.75rem; color:var(--text-dim);">🏙️ ${escapeHtml(hotel.city)}, ${escapeHtml(hotel.country)} ${hotel.postal_code} • ⭐ ${hotel.rating_avg.toFixed(1)} • ${hotel.total_reviews} reviews</div>
              </div>
            `;
          }
          dropdown.innerHTML = html;
          dropdown.style.display = "block";
          infoBox.innerText = `Found ${data.count} hotels in India (🇮🇳 Restricted to India only).`;
        } else {
          dropdown.style.display = "none";
          infoBox.innerText = "No hotels found in India matching query.";
        }
      } catch (err) {
        dropdown.style.display = "none";
        infoBox.innerText = "Error searching hotels.";
        console.error("Hotel search error:", err);
      }
    }, 300);
  };

  window.selectHotel = (hotelName, hotelDataJson) => {
    const hotelData = JSON.parse(hotelDataJson);
    document.getElementById("srHotelName").value = hotelName;
    document.getElementById("hotelAutocompleteDropdown").style.display = "none";
    
    // Display hotel address and map
    const addressDiv = document.getElementById("hotelAddressDisplay");
    addressDiv.innerHTML = `
      <strong>📍 ${escapeHtml(hotelData.address)}</strong><br>
      🏙️ ${escapeHtml(hotelData.city)}, ${escapeHtml(hotelData.postal_code)}, ${escapeHtml(hotelData.country)}<br>
      ⭐ Rating: ${hotelData.rating_avg.toFixed(1)} • ${hotelData.total_reviews} reviews
    `;
    addressDiv.style.display = "block";
    
    // Display Google Map with hotel location
    if (hotelData.latitude && hotelData.longitude) {
      const mapIframe = document.getElementById("hotelMapFrame");
      const mapContainer = document.getElementById("hotelMapContainer");
      // Use Google Maps embed with marker at hotel location
      const mapUrl = `https://www.google.com/maps/embed/v1/place?key=AIzaSyBFW0KW4w-Q7kOKXx-TjvJPYAIz8UcXW0M&q=${encodeURIComponent(hotelData.address + ', ' + hotelData.city + ', ' + hotelData.country)}`;
      mapIframe.src = mapUrl;
      mapContainer.style.display = "block";
    }
    
    document.getElementById("hotelResultsInfo").innerText = `✅ Selected: ${hotelName} (${hotelData.city}, ${hotelData.country})`;
  };

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.matches("#srHotelName")) {
      document.getElementById("hotelAutocompleteDropdown").style.display = "none";
    }
  });

  window.handleStudentReviewSubmit = async (e) => {
    e.preventDefault();
    const feedback = document.getElementById("srFeedback");
    feedback.innerText = "Submitting & running sentiment classifier...";
    feedback.style.color = "var(--accent-primary)";

    const hotel_name = document.getElementById("srHotelName").value;
    const rating = document.getElementById("srRating").value;
    const review_text = document.getElementById("srReviewText").value;

    try {
      const res = await fetch("/api/student/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hotel_name, rating, review_text })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        feedback.innerText = `✅ Submitted! Sentiment Classified as '${data.review.predicted_sentiment.toUpperCase()}'.`;
        feedback.style.color = "var(--pos-color)";
        document.getElementById("srReviewText").value = "";

        // Refresh reviews list & admin student reviews view if open
        fetchReviews(1);
        if (state.user && state.user.role === "owner") {
          fetchAdminStudents(state.adminSearchQuery);
        }
      } else {
        feedback.innerText = "❌ Error: " + (data.message || "Submission failed.");
        feedback.style.color = "var(--neg-color)";
      }
    } catch (err) {
      feedback.innerText = "❌ Network error: " + err.message;
      feedback.style.color = "var(--neg-color)";
    }
  };

  // --- OWNER ADMIN STUDENTS DEBOUNCED SEARCH & EXPANDABLE REVIEWS ---
  function setupAdminSearchListener() {
    const searchInput = document.getElementById("adminStudentSearch");
    if (!searchInput) return;

    let adminSearchTimeout = null;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(adminSearchTimeout);
      adminSearchTimeout = setTimeout(() => {
        state.adminSearchQuery = e.target.value;
        fetchAdminStudents(e.target.value);
      }, 300);
    });
  }

  async function fetchAdminStudents(searchQuery = "") {
    try {
      const url = searchQuery ? `/api/admin/students?search=${encodeURIComponent(searchQuery)}` : "/api/admin/students";
      const res = await fetch(url);
      if (!res.ok) {
        console.warn("Could not fetch admin students:", res.status);
        return;
      }
      const data = await res.json();
      const tbody = document.getElementById("adminStudentsTbody");

      if (!data.students || data.students.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1rem;">No matching registered students found.</td></tr>`;
        return;
      }

      let rowsHtml = "";
      for (const s of data.students) {
        const isExpanded = state.expandedStudentId === s.id;
        rowsHtml += `
          <tr style="cursor:pointer;" onclick="toggleStudentReviews(${s.id})">
            <td style="font-weight:600; color:var(--text-muted);">#${s.id}</td>
            <td style="font-weight:600; color:var(--accent-primary);">🎓 ${escapeHtml(s.name)}</td>
            <td>${escapeHtml(s.email)}</td>
            <td><span class="badge positive">${s.role}</span></td>
            <td style="font-size:0.8rem; color:var(--text-dim);">${s.created_at}</td>
            <td style="font-size:0.8rem; color:var(--text-dim);">${s.last_login || "Never"}</td>
            <td>
              <button class="btn btn-outline" style="padding:0.25rem 0.6rem; font-size:0.75rem;">
                ${isExpanded ? '▲ Hide Reviews' : '▼ Inspect Reviews'}
              </button>
            </td>
          </tr>
        `;

        if (isExpanded) {
          rowsHtml += `
            <tr id="studentReviewsRow_${s.id}">
              <td colspan="7" style="background:var(--bg-secondary); padding:1rem; border-left:3px solid var(--accent-primary);">
                <div id="studentReviewsContainer_${s.id}">
                  <span style="font-size:0.85rem; color:var(--text-muted);">Loading submitted hotel reviews for ${escapeHtml(s.name)}...</span>
                </div>
              </td>
            </tr>
          `;
        }
      }

      tbody.innerHTML = rowsHtml;

      if (state.expandedStudentId) {
        loadStudentReviewsInline(state.expandedStudentId);
      }
    } catch (e) {
      console.error("Error fetching admin students:", e);
    }
  }

  window.toggleStudentReviews = (studentId) => {
    if (state.expandedStudentId === studentId) {
      state.expandedStudentId = null;
    } else {
      state.expandedStudentId = studentId;
    }
    fetchAdminStudents(state.adminSearchQuery);
  };

  async function loadStudentReviewsInline(studentId) {
    const container = document.getElementById(`studentReviewsContainer_${studentId}`);
    if (!container) return;

    try {
      const res = await fetch(`/api/admin/students/${studentId}/reviews`);
      const data = await res.json();

      if (!res.ok || !data.success) {
        container.innerHTML = `<span style="color:var(--neg-color);">Failed to load student reviews.</span>`;
        return;
      }

      if (!data.reviews || data.reviews.length === 0) {
        container.innerHTML = `
          <div style="font-size:0.85rem; color:var(--text-muted);">
            ℹ️ No hotel reviews submitted yet by <strong>${escapeHtml(data.student.name)}</strong>.
          </div>
        `;
        return;
      }

      let tableHtml = `
        <div style="margin-bottom:0.5rem; font-weight:700; font-size:0.85rem; color:var(--accent-primary);">
          🏨 Submitted Hotel Reviews by ${escapeHtml(data.student.name)} (${data.reviews.length} Total):
        </div>
        <table class="review-table" style="background:var(--card); box-shadow:none;">
          <thead>
            <tr>
              <th>Hotel Name</th>
              <th>Review Text</th>
              <th>Rating</th>
              <th>Model Sentiment</th>
              <th>Submitted Date</th>
            </tr>
          </thead>
          <tbody>
      `;

      tableHtml += data.reviews.map(r => `
        <tr>
          <td style="font-weight:600;">🏨 ${escapeHtml(r.hotel_name)}</td>
          <td style="font-size:0.85rem;">"${escapeHtml(r.review_text)}"</td>
          <td style="white-space:nowrap;">${"⭐".repeat(r.rating)}</td>
          <td><span class="badge ${r.predicted_sentiment}">${r.predicted_sentiment}</span></td>
          <td style="font-size:0.75rem; color:var(--text-dim);">${r.submitted_at}</td>
        </tr>
      `).join("");

      tableHtml += `</tbody></table>`;
      container.innerHTML = tableHtml;
    } catch (e) {
      container.innerHTML = `<span style="color:var(--neg-color);">Error fetching reviews: ${e.message}</span>`;
    }
  }

  // --- FETCH SUMMARY & METRICS ---
  async function fetchSummaryData() {
    try {
      const res = await fetch("/api/summary");
      const data = await res.json();

      document.getElementById("totalReviewsVal").innerText = data.total_reviews ? data.total_reviews.toLocaleString() : "20,491";
      document.getElementById("avgRatingVal").innerText = `${data.avg_rating || 3.95} ⭐`;
      document.getElementById("modelAccVal").innerText = `${data.accuracy || 82.48}%`;

      renderSentimentDoughnut(data.sentiment_counts);
      renderRatingDistribution(data.rating_counts);
      renderConfusionMatrix(data.confusion_matrix, data.classes);
      renderTrendsLineChart(data.trends);
    } catch (e) {
      console.error("Error fetching summary:", e);
    }
  }

  // --- CHARTS (CHART.JS) ---
  function renderSentimentDoughnut(counts) {
    const ctx = document.getElementById("sentimentDoughnutChart").getContext("2d");
    if (state.charts.doughnut) state.charts.doughnut.destroy();

    state.charts.doughnut = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Positive", "Neutral", "Negative"],
        datasets: [{
          data: [counts.positive || 15093, counts.neutral || 2184, counts.negative || 3214],
          backgroundColor: ["#34d399", "#f59e0b", "#f87171"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: "#9ca3af", font: { weight: "600" } } }
        },
        cutout: "70%"
      }
    });
  }

  function renderRatingDistribution(ratings) {
    const ctx = document.getElementById("ratingBarChart").getContext("2d");
    if (state.charts.bar) state.charts.bar.destroy();

    state.charts.bar = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["1 Star", "2 Stars", "3 Stars", "4 Stars", "5 Stars"],
        datasets: [{
          label: "Review Count",
          data: [
            ratings["1"] || 1421,
            ratings["2"] || 1793,
            ratings["3"] || 2184,
            ratings["4"] || 6039,
            ratings["5"] || 9054
          ],
          backgroundColor: ["#f87171", "#fb923c", "#f59e0b", "#a3e635", "#34d399"],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
          y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255, 255, 255, 0.06)" } }
        }
      }
    });
  }

  function renderConfusionMatrix(matrix, classes) {
    const container = document.getElementById("confusionMatrixGrid");
    if (!matrix || matrix.length === 0) return;

    let html = `<table style="width:100%; border-collapse:collapse; text-align:center; font-size:0.85rem;">
      <thead>
        <tr>
          <th style="padding:0.5rem; color:var(--text-muted);">Actual \\ Pred</th>
          <th style="padding:0.5rem; color:var(--neg-color);">Negative</th>
          <th style="padding:0.5rem; color:var(--neu-color);">Neutral</th>
          <th style="padding:0.5rem; color:var(--pos-color);">Positive</th>
        </tr>
      </thead>
      <tbody>`;

    const rowLabels = ["Negative", "Neutral", "Positive"];
    const colors = [
      ["rgba(248, 113, 113, 0.15)", "rgba(255, 255, 255, 0.02)", "rgba(255, 255, 255, 0.02)"],
      ["rgba(255, 255, 255, 0.02)", "rgba(251, 191, 36, 0.15)", "rgba(255, 255, 255, 0.02)"],
      ["rgba(255, 255, 255, 0.02)", "rgba(255, 255, 255, 0.02)", "rgba(52, 211, 153, 0.15)"]
    ];
    const textColors = [
      ["var(--neg-color)", "var(--text-muted)", "var(--text-muted)"],
      ["var(--text-muted)", "var(--neu-color)", "var(--text-muted)"],
      ["var(--text-muted)", "var(--text-muted)", "var(--pos-color)"]
    ];

    for (let r = 0; r < matrix.length; r++) {
      html += `<tr><td style="padding:0.6rem; font-weight:700; color:var(--text-muted);">${rowLabels[r]}</td>`;
      for (let c = 0; c < matrix[r].length; c++) {
        const val = matrix[r][c];
        const bg = colors[r][c];
        const tc = textColors[r][c];
        html += `<td style="padding:0.6rem; background:${bg}; color:${tc}; border:1px solid var(--line); font-weight:bold;">${val}</td>`;
      }
      html += `</tr>`;
    }
    html += `</tbody></table>`;
    container.innerHTML = html;
  }

  function renderTrendsLineChart(trends) {
    const ctx = document.getElementById("trendLineChart").getContext("2d");
    if (state.charts.trend) state.charts.trend.destroy();
    if (!trends) return;

    state.charts.trend = new Chart(ctx, {
      type: "line",
      data: {
        labels: trends.map(t => t.month),
        datasets: [
          {
            label: "Positive",
            data: trends.map(t => t.positive),
            borderColor: "#34d399",
            backgroundColor: "#34d399",
            tension: 0.3,
            fill: false
          },
          {
            label: "Neutral",
            data: trends.map(t => t.neutral),
            borderColor: "#f59e0b",
            backgroundColor: "#f59e0b",
            tension: 0.3,
            fill: false
          },
          {
            label: "Negative",
            data: trends.map(t => t.negative),
            borderColor: "#f87171",
            backgroundColor: "#f87171",
            tension: 0.3,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top", labels: { color: "#9ca3af" } } },
        scales: {
          x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
          y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255, 255, 255, 0.06)" } }
        }
      }
    });
  }

  // --- THEMES (LDA TOPICS) ---
  async function fetchThemes() {
    try {
      const res = await fetch("/api/themes");
      const data = await res.json();
      const container = document.getElementById("themesContainer");

      if (!data.themes || data.themes.length === 0) {
        container.innerHTML = `<p style="color:var(--text-muted);">No extracted topics found.</p>`;
        return;
      }

      container.innerHTML = data.themes.map(t => `
        <div class="theme-card">
          <span class="theme-badge">Theme #${t.id} Complaint Cluster</span>
          <h4 class="theme-title">${t.title}</h4>
          <div class="keywords-container">
            ${t.keywords.map(k => `<span class="keyword-tag">${k}</span>`).join("")}
          </div>
          <div class="sample-snippet">
            "${t.sample_snippets[0] || 'Representative negative review...'}"
          </div>
        </div>
      `).join("");
    } catch (e) {
      console.error("Error fetching themes:", e);
    }
  }

  // --- LIVE PREDICTION SANDBOX ---
  function setupSandboxListeners() {
    const textInput = document.getElementById("sandboxInput");
    const btn = document.getElementById("analyzeBtn");

    btn.addEventListener("click", () => runPrediction(textInput.value));

    window.loadPreset = (text) => {
      textInput.value = text;
      runPrediction(text);
    };
  }

  async function runPrediction(text) {
    if (!text.trim()) return;

    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review: text })
      });
      const data = await res.json();

      if (data.error) {
        alert("Prediction error: " + data.error);
        return;
      }

      const badge = document.getElementById("predBadge");
      const sentiment = data.predicted_sentiment;
      badge.className = `pred-result-badge ${sentiment}`;
      const emojiMap = { positive: "😄 Positive", neutral: "😐 Neutral", negative: "😠 Negative" };
      badge.innerText = emojiMap[sentiment] || sentiment;

      const conf = data.confidence;
      updateConfBar("posBar", "posPercent", conf.positive || 0);
      updateConfBar("neuBar", "neuPercent", conf.neutral || 0);
      updateConfBar("negBar", "negPercent", conf.negative || 0);

      const wordsContainer = document.getElementById("contributingWords");
      if (data.top_contributing_words && data.top_contributing_words.length > 0) {
        wordsContainer.innerHTML = data.top_contributing_words.map(w => `
          <span class="keyword-tag">
            ${w.word} (${w.weight > 0 ? '+' : ''}${w.weight})
          </span>
        `).join(" ");
      } else {
        wordsContainer.innerText = "No specific high-weight n-grams identified.";
      }
    } catch (e) {
      console.error("Prediction API error:", e);
    }
  }

  function updateConfBar(barId, percentId, val) {
    document.getElementById(barId).style.width = `${val}%`;
    document.getElementById(percentId).innerText = `${val.toFixed(1)}%`;
  }

  // --- REVIEWS DATA TABLE ---
  async function fetchReviews(page = 1) {
    state.reviewsPage = page;
    const { sentiment, rating, search } = state.reviewsFilter;

    const url = `/api/reviews?page=${page}&per_page=10&sentiment=${sentiment}&rating=${rating}&search=${encodeURIComponent(search)}`;

    try {
      const res = await fetch(url);
      const data = await res.json();

      const tbody = document.getElementById("reviewsTbody");
      if (!data.reviews || data.reviews.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:2rem;">No matching reviews found.</td></tr>`;
        document.getElementById("pageInfo").innerText = "Page 0 of 0";
        return;
      }

      tbody.innerHTML = data.reviews.map(r => `
        <tr>
          <td style="font-weight:600; color:var(--text-muted);">#${r.id}</td>
          <td>${escapeHtml(r.review)}</td>
          <td style="white-space:nowrap;">${"⭐".repeat(r.rating)}</td>
          <td><span class="badge ${r.sentiment}">${r.sentiment}</span></td>
        </tr>
      `).join("");

      document.getElementById("pageInfo").innerText = `Page ${data.page} of ${data.total_pages} (${data.total.toLocaleString()} total)`;
      document.getElementById("prevPageBtn").disabled = data.page <= 1;
      document.getElementById("nextPageBtn").disabled = data.page >= data.total_pages;
    } catch (e) {
      console.error("Error fetching reviews:", e);
    }
  }

  document.getElementById("sentimentFilter").addEventListener("change", (e) => {
    state.reviewsFilter.sentiment = e.target.value;
    fetchReviews(1);
  });

  document.getElementById("ratingFilter").addEventListener("change", (e) => {
    state.reviewsFilter.rating = e.target.value;
    fetchReviews(1);
  });

  let searchTimeout = null;
  document.getElementById("searchInput").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.reviewsFilter.search = e.target.value;
      fetchReviews(1);
    }, 300);
  });

  document.getElementById("prevPageBtn").addEventListener("click", () => {
    if (state.reviewsPage > 1) fetchReviews(state.reviewsPage - 1);
  });

  document.getElementById("nextPageBtn").addEventListener("click", () => {
    fetchReviews(state.reviewsPage + 1);
  });

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
});
