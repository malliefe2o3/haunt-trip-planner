/* ==========================================================================
   Haunt Trip Planner — Frontend JavaScript
   ========================================================================== */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
var blackoutDates = [];
var legs = [];
var attractions = [];
var scrapedResults = [];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(timeStr) {
    // Convert "19:00" to "7:00 PM"
    if (!timeStr) return "";
    var parts = timeStr.split(":");
    var hour = parseInt(parts[0], 10);
    var minute = parts[1] || "00";
    var ampm = hour >= 12 ? "PM" : "AM";
    if (hour === 0) hour = 12;
    else if (hour > 12) hour -= 12;
    return hour + ":" + minute + " " + ampm;
}

function showStatus(elementId, message, isError) {
    var el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.className = "status-message " + (isError ? "error" : "success");
    el.style.display = "block";
}

// ---------------------------------------------------------------------------
// Setup: Blackout Dates
// ---------------------------------------------------------------------------

function addBlackout() {
    var input = document.getElementById("blackout-input");
    if (!input || !input.value) return;
    var d = input.value;
    if (blackoutDates.indexOf(d) === -1) {
        blackoutDates.push(d);
    }
    input.value = "";
    renderBlackouts();
}

function removeBlackout(index) {
    blackoutDates.splice(index, 1);
    renderBlackouts();
}

function renderBlackouts() {
    var container = document.getElementById("blackout-list");
    if (!container) return;
    container.innerHTML = "";
    blackoutDates.forEach(function(d, i) {
        var tag = document.createElement("span");
        tag.className = "tag";
        tag.innerHTML = d + ' <span class="remove-tag" onclick="removeBlackout(' + i + ')">x</span>';
        container.appendChild(tag);
    });
}

// ---------------------------------------------------------------------------
// Setup: Legs
// ---------------------------------------------------------------------------

function addLeg() {
    legs.push({
        start: "",
        end: "",
        startLocation: "",
        endLocation: ""
    });
    renderLegs();
}

function removeLeg(index) {
    legs.splice(index, 1);
    renderLegs();
}

function renderLegs() {
    var container = document.getElementById("legs-list");
    if (!container) return;
    container.innerHTML = "";
    legs.forEach(function(leg, i) {
        var card = document.createElement("div");
        card.className = "leg-card";
        card.innerHTML =
            '<div class="leg-header"><h3>Leg ' + (i + 1) + '</h3>' +
            '<button class="btn btn-danger" onclick="removeLeg(' + i + ')">Remove</button></div>' +
            '<div class="form-row">' +
            '<div class="form-group"><label>Start Date</label>' +
            '<input type="date" onchange="legs[' + i + '].start=this.value" value="' + leg.start + '"></div>' +
            '<div class="form-group"><label>End Date</label>' +
            '<input type="date" onchange="legs[' + i + '].end=this.value" value="' + leg.end + '"></div>' +
            '</div>' +
            '<div class="form-row">' +
            '<div class="form-group"><label>Start Location</label>' +
            '<input type="text" onchange="legs[' + i + '].startLocation=this.value" value="' + leg.startLocation + '" placeholder="City, State"></div>' +
            '<div class="form-group"><label>End Location</label>' +
            '<input type="text" onchange="legs[' + i + '].endLocation=this.value" value="' + leg.endLocation + '" placeholder="City, State"></div>' +
            '</div>';
        container.appendChild(card);
    });
}

// ---------------------------------------------------------------------------
// Setup: Save Trip
// ---------------------------------------------------------------------------

function saveTrip() {
    var startDate = document.getElementById("start-date").value;
    var endDate = document.getElementById("end-date").value;
    var startLoc = document.getElementById("start-location").value;
    var endLoc = document.getElementById("end-location").value;
    var apiKey = document.getElementById("api-key").value;

    if (!startDate || !endDate || !startLoc || !endLoc) {
        showStatus("setup-status", "Please fill in all required fields.", true);
        return;
    }

    var tripData = {
        date_range: { start: startDate, end: endDate },
        start_location: startLoc,
        end_location: endLoc,
        blackout_dates: blackoutDates,
        legs: legs.map(function(l) {
            return {
                date_range: { start: l.start, end: l.end },
                start_location: l.startLocation,
                end_location: l.endLocation
            };
        })
    };

    // Save API key if provided
    var promises = [];
    if (apiKey) {
        promises.push(
            fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ claude_api_key: apiKey })
            })
        );
    }

    promises.push(
        fetch("/api/trip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(tripData)
        })
    );

    Promise.all(promises)
        .then(function(responses) {
            return responses[responses.length - 1].json();
        })
        .then(function(data) {
            if (data.status === "ok") {
                showStatus("setup-status", "Trip saved! Proceeding to attractions...", false);
                setTimeout(function() {
                    window.location.href = "/attractions";
                }, 800);
            } else {
                showStatus("setup-status", "Error saving trip: " + JSON.stringify(data), true);
            }
        })
        .catch(function(err) {
            showStatus("setup-status", "Network error: " + err.message, true);
        });
}

// ---------------------------------------------------------------------------
// Attractions: Add & List
// ---------------------------------------------------------------------------

function addAttraction() {
    var name = document.getElementById("attr-name").value.trim();
    var address = document.getElementById("attr-address").value.trim();
    var url = document.getElementById("attr-url").value.trim();

    if (!name || !address) {
        showStatus("attr-status", "Name and address are required.", true);
        return;
    }

    var attrData = {
        name: name,
        address: address,
        schedule_url: url,
        assigned_dates: []
    };

    fetch("/api/attractions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(attrData)
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.status === "ok") {
            attractions.push({ name: name, address: address, url: url });
            renderAttractions();
            document.getElementById("attr-name").value = "";
            document.getElementById("attr-address").value = "";
            document.getElementById("attr-url").value = "";
            showStatus("attr-status", "Added: " + name, false);
        } else {
            showStatus("attr-status", "Error: " + JSON.stringify(data), true);
        }
    })
    .catch(function(err) {
        showStatus("attr-status", "Network error: " + err.message, true);
    });
}

function renderAttractions() {
    var container = document.getElementById("attractions-list");
    if (!container) return;
    if (attractions.length === 0) {
        container.innerHTML = '<p class="empty-state">No attractions added yet.</p>';
        return;
    }
    container.innerHTML = "";
    attractions.forEach(function(a) {
        var item = document.createElement("div");
        item.className = "attraction-item";
        item.innerHTML =
            '<div><span class="name">' + a.name + '</span><br>' +
            '<span class="address">' + a.address + '</span></div>';
        container.appendChild(item);
    });
}

function submitAttractions() {
    window.location.href = "/review";
}

// ---------------------------------------------------------------------------
// Review: Load Scraped Data
// ---------------------------------------------------------------------------

function loadReview() {
    fetch("/api/scrape", { method: "POST" })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            scrapedResults = data.results || [];
            renderReview();
            // If we're on the loading page, redirect to review
            if (window.location.pathname === "/loading") {
                window.location.href = "/review";
            }
        })
        .catch(function(err) {
            var container = document.getElementById("review-cards");
            if (container) {
                container.innerHTML = '<p class="empty-state">Could not load scraped data. You can still set schedules manually.</p>';
            }
            renderReview();
        });
}

function renderReview() {
    var container = document.getElementById("review-cards");
    if (!container) return;

    if (!scrapedResults || scrapedResults.length === 0) {
        container.innerHTML = '<p class="empty-state">No attractions to review. Add attractions first.</p>';
        return;
    }

    container.innerHTML = "";
    scrapedResults.forEach(function(result, idx) {
        var card = document.createElement("div");
        card.className = "review-card";

        var badgeClass = "badge-" + result.confidence;
        var header = '<div class="review-header"><h3>' + result.name + '</h3>' +
            '<span class="badge ' + badgeClass + '">' + result.confidence + '</span></div>';

        // Build editable schedule table
        var table = '<table class="schedule-table"><thead><tr>' +
            '<th>Date</th><th>Open</th><th>Close</th><th>Price</th><th>Ticket URL</th>' +
            '</tr></thead><tbody>';

        var dates = result.dates || [];
        var times = result.time_ranges || [];
        var prices = result.prices || [];
        var ticketUrls = result.ticket_urls || [];

        if (dates.length === 0) {
            table += '<tr><td colspan="5" style="color:#666">No dates found. Add manually below.</td></tr>';
        }

        dates.forEach(function(d, i) {
            var openT = times[0] ? times[0][0] : "19:00";
            var closeT = times[0] ? times[0][1] : "23:00";
            var price = prices[0] || "";
            var tUrl = ticketUrls[0] || "";
            table += '<tr>' +
                '<td><input type="date" value="' + d + '" data-attr="' + idx + '" data-row="' + i + '" data-field="date"></td>' +
                '<td><input type="time" value="' + openT + '" data-attr="' + idx + '" data-row="' + i + '" data-field="open"></td>' +
                '<td><input type="time" value="' + closeT + '" data-attr="' + idx + '" data-row="' + i + '" data-field="close"></td>' +
                '<td><input type="number" value="' + price + '" data-attr="' + idx + '" data-row="' + i + '" data-field="price" step="0.01"></td>' +
                '<td><input type="url" value="' + tUrl + '" data-attr="' + idx + '" data-row="' + i + '" data-field="ticket" placeholder="https://..."></td>' +
                '</tr>';
        });

        table += '</tbody></table>';

        card.innerHTML = header + table;
        container.appendChild(card);
    });

    var btn = document.getElementById("generate-btn");
    if (btn) btn.disabled = false;
}

// ---------------------------------------------------------------------------
// Review: Generate Itinerary
// ---------------------------------------------------------------------------

function generateItinerary() {
    var btn = document.getElementById("generate-btn");
    if (btn) btn.disabled = true;
    showStatus("review-status", "Saving schedules and optimizing...", false);

    // Collect schedule data from review cards
    var promises = [];
    scrapedResults.forEach(function(result, idx) {
        var rows = document.querySelectorAll('input[data-attr="' + idx + '"]');
        var scheduleMap = {};

        rows.forEach(function(input) {
            var row = input.getAttribute("data-row");
            var field = input.getAttribute("data-field");
            if (!scheduleMap[row]) {
                scheduleMap[row] = {};
            }
            scheduleMap[row][field] = input.value;
        });

        var schedule = [];
        Object.keys(scheduleMap).forEach(function(row) {
            var r = scheduleMap[row];
            if (r.date) {
                schedule.push({
                    date: r.date,
                    open_time: r.open || "19:00",
                    close_time: r.close || "23:00",
                    price: r.price ? parseFloat(r.price) : null,
                    ticket_url: r.ticket || null
                });
            }
        });

        if (schedule.length > 0) {
            promises.push(
                fetch("/api/schedule", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: result.name, schedule: schedule })
                })
            );
        }
    });

    Promise.all(promises)
        .then(function() {
            return fetch("/api/optimize", { method: "POST" });
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            showStatus("review-status", "Itinerary generated! Redirecting...", false);
            setTimeout(function() {
                window.location.href = "/itinerary";
            }, 800);
        })
        .catch(function(err) {
            showStatus("review-status", "Error: " + err.message, true);
            if (btn) btn.disabled = false;
        });
}

// ---------------------------------------------------------------------------
// Itinerary: Load & Render
// ---------------------------------------------------------------------------

function loadItinerary() {
    fetch("/api/optimize", { method: "POST" })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            renderItinerary(data);
            loadDiscoverySuggestions();
        })
        .catch(function(err) {
            var container = document.getElementById("itinerary-content");
            if (container) {
                container.innerHTML = '<p class="empty-state">Could not load itinerary: ' + err.message + '</p>';
            }
        });
}

function renderItinerary(data) {
    var container = document.getElementById("itinerary-content");
    if (!container) return;
    container.innerHTML = "";

    var scheduled = data.scheduled || {};
    var unscheduled = data.unscheduled || [];

    var dates = Object.keys(scheduled).sort();
    var tripTotal = 0;

    if (dates.length === 0 && unscheduled.length === 0) {
        container.innerHTML = '<p class="empty-state">No itinerary data. Go back to add attractions and generate.</p>';
        return;
    }

    // Populate adjust dropdown
    var adjustSelect = document.getElementById("adjust-name");
    if (adjustSelect) {
        adjustSelect.innerHTML = '<option value="">Select attraction...</option>';
    }

    dates.forEach(function(d) {
        var header = document.createElement("div");
        header.className = "date-header";
        header.textContent = d;
        container.appendChild(header);

        var nightlyTotal = 0;
        scheduled[d].forEach(function(entry) {
            var div = document.createElement("div");
            div.className = "haunt-entry";

            var priceHtml = "";
            if (entry.price !== null && entry.price !== undefined) {
                nightlyTotal += entry.price;
                if (entry.ticket_url) {
                    priceHtml = '<div class="haunt-price">$' + entry.price.toFixed(2) +
                        ' &mdash; <a href="' + entry.ticket_url + '" target="_blank">Buy Tickets</a></div>';
                } else {
                    priceHtml = '<div class="haunt-price">$' + entry.price.toFixed(2) + '</div>';
                }
            }

            div.innerHTML =
                '<div class="haunt-name">' + entry.name + '</div>' +
                '<div class="haunt-time">Arrive: ' + formatTime(entry.arrival_time) +
                ' | Open: ' + formatTime(entry.open_time) +
                ' - ' + formatTime(entry.close_time) + '</div>' +
                priceHtml;

            container.appendChild(div);

            // Add to adjust dropdown
            if (adjustSelect) {
                var opt = document.createElement("option");
                opt.value = entry.name;
                opt.textContent = entry.name;
                // Avoid duplicates
                var exists = false;
                for (var i = 0; i < adjustSelect.options.length; i++) {
                    if (adjustSelect.options[i].value === entry.name) {
                        exists = true;
                        break;
                    }
                }
                if (!exists) adjustSelect.appendChild(opt);
            }
        });

        if (nightlyTotal > 0) {
            var subtotal = document.createElement("div");
            subtotal.className = "subtotal";
            subtotal.textContent = "Nightly Total: $" + nightlyTotal.toFixed(2);
            container.appendChild(subtotal);
        }
        tripTotal += nightlyTotal;
    });

    if (tripTotal > 0) {
        var total = document.createElement("div");
        total.className = "trip-total";
        total.textContent = "Trip Total: $" + tripTotal.toFixed(2);
        container.appendChild(total);
    }

    // Unscheduled
    if (unscheduled.length > 0) {
        var section = document.createElement("div");
        section.className = "unscheduled-section";
        section.innerHTML = "<h3>Could Not Schedule</h3>";
        unscheduled.forEach(function(item) {
            var div = document.createElement("div");
            div.className = "unscheduled-item";
            div.innerHTML = "<strong>" + item.name + "</strong> &mdash; " + item.reason;
            section.appendChild(div);
        });
        container.appendChild(section);
    }

    // Show adjust panel
    var adjustPanel = document.getElementById("adjust-panel");
    if (adjustPanel && dates.length > 0) {
        adjustPanel.style.display = "block";
    }
}

// ---------------------------------------------------------------------------
// Itinerary: Adjust
// ---------------------------------------------------------------------------

function populateAdjustDropdown() {
    var nameSelect = document.getElementById("adjust-name");
    var dateSelect = document.getElementById("adjust-date");
    if (!nameSelect || !dateSelect) return;

    var name = nameSelect.value;
    dateSelect.innerHTML = '<option value="">Loading...</option>';

    if (!name) {
        dateSelect.innerHTML = '<option value="">Select attraction first</option>';
        return;
    }

    fetch("/api/eligible-dates?name=" + encodeURIComponent(name))
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            dateSelect.innerHTML = '<option value="">Select date...</option>';
            (data.dates || []).forEach(function(d) {
                var opt = document.createElement("option");
                opt.value = d;
                opt.textContent = d;
                dateSelect.appendChild(opt);
            });
        })
        .catch(function() {
            dateSelect.innerHTML = '<option value="">Error loading dates</option>';
        });
}

function adjustSchedule() {
    var name = document.getElementById("adjust-name").value;
    var adjustDate = document.getElementById("adjust-date").value;
    if (!name || !adjustDate) return;

    fetch("/api/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name, date: adjustDate })
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        renderItinerary(data);
    })
    .catch(function(err) {
        alert("Error adjusting: " + err.message);
    });
}

// ---------------------------------------------------------------------------
// Discovery Suggestions
// ---------------------------------------------------------------------------

function loadDiscoverySuggestions() {
    fetch("/api/discover", { method: "POST" })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            var panel = document.getElementById("discovery-panel");
            var content = document.getElementById("discovery-content");
            if (!panel || !content) return;

            var gaps = data.gaps || [];
            var suggestions = data.suggestions || [];

            if (gaps.length === 0 && suggestions.length === 0) return;

            panel.style.display = "block";
            content.innerHTML = "";

            if (gaps.length > 0) {
                var gapSection = document.createElement("div");
                gapSection.innerHTML = "<h3>Open Nights</h3>";
                var gapList = document.createElement("div");
                gapList.className = "gap-list";
                gaps.forEach(function(d) {
                    var span = document.createElement("span");
                    span.className = "gap-date";
                    span.textContent = d;
                    gapList.appendChild(span);
                });
                gapSection.appendChild(gapList);
                content.appendChild(gapSection);
            }

            suggestions.forEach(function(s) {
                var div = document.createElement("div");
                div.className = "suggestion";
                div.innerHTML =
                    '<div class="suggestion-name">' + s.name + '</div>' +
                    '<div class="suggestion-detail">' +
                    (s.date ? "Suggested date: " + s.date + " | " : "") +
                    s.distance + " miles away | " +
                    s.type.replace("_", " ") +
                    '</div>' +
                    (s.url ? '<a href="' + s.url + '" target="_blank">View Website</a>' : "");
                content.appendChild(div);
            });
        })
        .catch(function() {
            // Silently fail for discovery
        });
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

function printItinerary() {
    window.print();
}

function downloadHtml() {
    var title = document.getElementById("export-title").value || "Haunt Trip";
    fetch("/api/export?title=" + encodeURIComponent(title))
        .then(function(resp) { return resp.text(); })
        .then(function(html) {
            var blob = new Blob([html], { type: "text/html" });
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = title.replace(/\s+/g, "_") + ".html";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        })
        .catch(function(err) {
            alert("Error downloading: " + err.message);
        });
}
