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
// Calendar Picker Component
// ---------------------------------------------------------------------------

var MONTH_NAMES = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"];
var DOW_LABELS = ["Su","Mo","Tu","We","Th","Fr","Sa"];

function CalendarPicker(containerId, opts) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;
    this.mode = opts.mode || "range"; // "range", "toggle", "single"
    this.onSelect = opts.onSelect || function(){};
    this.onConfirm = opts.onConfirm || function(){};
    this.onEdit = opts.onEdit || null;
    this.renderExtra = opts.renderExtra || null;
    this.selected = opts.selected || []; // for toggle mode
    this.rangeStart = opts.rangeStart || null;
    this.rangeEnd = opts.rangeEnd || null;
    this.selectingEnd = false;
    this.collapsed = false;
    this.viewYear = opts.initialYear || 2026;
    this.viewMonth = opts.initialMonth != null ? opts.initialMonth : 8; // 0-indexed (8 = September)
    this.render();
}

function formatDate(isoStr) {
    if (!isoStr) return "—";
    var parts = isoStr.split("-");
    return parseInt(parts[1], 10) + "/" + parseInt(parts[2], 10);
}

CalendarPicker.prototype.getSummary = function() {
    if (this.mode === "range") {
        if (this.rangeStart && this.rangeEnd) {
            return formatDate(this.rangeStart) + "  to  " + formatDate(this.rangeEnd);
        } else if (this.rangeStart) {
            return formatDate(this.rangeStart) + "  to  —";
        }
        return "No dates selected";
    } else if (this.mode === "toggle") {
        if (this.selected.length === 0) return "No dates selected";
        var sorted = this.selected.slice().sort();
        if (sorted.length <= 3) return sorted.map(formatDate).join(", ");
        return sorted.length + " dates selected";
    }
    return "No dates selected";
};

CalendarPicker.prototype.render = function() {
    var self = this;
    var container = this.container;
    container.innerHTML = "";
    container.className = "calendar-picker";

    if (this.collapsed) {
        var summary = document.createElement("div");
        summary.className = "cal-summary";
        summary.innerHTML = '<span class="cal-summary-text">' + this.getSummary() + '</span>' +
            '<button type="button" class="btn btn-secondary cal-edit-btn">Edit</button>';
        summary.querySelector(".cal-edit-btn").onclick = function() {
            self.collapsed = false;
            if (self.onEdit) self.onEdit();
            self.render();
        };
        container.appendChild(summary);
        return;
    }

    var header = document.createElement("div");
    header.className = "cal-header";

    var prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "cal-nav";
    prevBtn.textContent = "◀";
    prevBtn.onclick = function() { self.prevMonth(); };

    var nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "cal-nav";
    nextBtn.textContent = "▶";
    nextBtn.onclick = function() { self.nextMonth(); };

    var title = document.createElement("span");
    title.className = "cal-title";
    title.textContent = MONTH_NAMES[this.viewMonth] + " " + this.viewYear;

    header.appendChild(prevBtn);
    header.appendChild(title);
    header.appendChild(nextBtn);
    container.appendChild(header);

    var grid = document.createElement("div");
    grid.className = "cal-grid";

    DOW_LABELS.forEach(function(d) {
        var dow = document.createElement("div");
        dow.className = "cal-dow";
        dow.textContent = d;
        grid.appendChild(dow);
    });

    var firstDay = new Date(this.viewYear, this.viewMonth, 1).getDay();
    var daysInMonth = new Date(this.viewYear, this.viewMonth + 1, 0).getDate();

    for (var i = 0; i < firstDay; i++) {
        var empty = document.createElement("div");
        empty.className = "cal-day empty";
        grid.appendChild(empty);
    }

    for (var d = 1; d <= daysInMonth; d++) {
        var dayEl = document.createElement("div");
        dayEl.className = "cal-day";
        dayEl.textContent = d;
        var dateStr = this.viewYear + "-" +
            String(this.viewMonth + 1).padStart(2, "0") + "-" +
            String(d).padStart(2, "0");
        dayEl.setAttribute("data-date", dateStr);

        if (this.mode === "range") {
            if (dateStr === this.rangeStart) dayEl.classList.add("selected");
            if (dateStr === this.rangeEnd) dayEl.classList.add("selected");
            if (this.rangeStart && this.rangeEnd && dateStr > this.rangeStart && dateStr < this.rangeEnd) {
                dayEl.classList.add("in-range");
            }
        } else if (this.mode === "toggle") {
            if (this.selected.indexOf(dateStr) !== -1) dayEl.classList.add("blackout");
        } else if (this.mode === "single") {
            if (this.selected.indexOf(dateStr) !== -1) dayEl.classList.add("selected");
        }

        (function(ds, el) {
            el.onclick = function() { self.handleClick(ds); };
        })(dateStr, dayEl);

        grid.appendChild(dayEl);
    }

    container.appendChild(grid);

    if (this.renderExtra) {
        var extraEl = document.createElement("div");
        extraEl.style.marginTop = "10px";
        this.renderExtra(extraEl);
        if (extraEl.hasChildNodes()) {
            container.appendChild(extraEl);
        }
    }

    var footer = document.createElement("div");
    footer.className = "cal-footer";

    if (this.mode === "range") {
        var display = document.createElement("span");
        display.className = "cal-selected-display";
        display.textContent = this.getSummary();
        footer.appendChild(display);
    }

    var confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "btn btn-primary cal-confirm-btn";
    confirmBtn.textContent = "Confirm";
    confirmBtn.onclick = function() {
        self.collapsed = true;
        self.onConfirm();
        self.render();
    };
    footer.appendChild(confirmBtn);

    container.appendChild(footer);
};

CalendarPicker.prototype.handleClick = function(dateStr) {
    if (this.mode === "range") {
        if (!this.selectingEnd || !this.rangeStart) {
            this.rangeStart = dateStr;
            this.rangeEnd = null;
            this.selectingEnd = true;
        } else {
            if (dateStr < this.rangeStart) {
                this.rangeEnd = this.rangeStart;
                this.rangeStart = dateStr;
            } else {
                this.rangeEnd = dateStr;
            }
            this.selectingEnd = false;
        }
        this.render();
        this.onSelect({ start: this.rangeStart, end: this.rangeEnd });
    } else if (this.mode === "toggle") {
        var idx = this.selected.indexOf(dateStr);
        if (idx === -1) {
            this.selected.push(dateStr);
        } else {
            this.selected.splice(idx, 1);
        }
        this.render();
        this.onSelect(this.selected);
    } else if (this.mode === "single") {
        this.selected = [dateStr];
        this.render();
        this.onSelect(dateStr);
    }
};

CalendarPicker.prototype.prevMonth = function() {
    this.viewMonth--;
    if (this.viewMonth < 0) { this.viewMonth = 11; this.viewYear--; }
    this.render();
};

CalendarPicker.prototype.nextMonth = function() {
    this.viewMonth++;
    if (this.viewMonth > 11) { this.viewMonth = 0; this.viewYear++; }
    this.render();
};

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
        tag.innerHTML = formatDate(d) + ' <span class="remove-tag" onclick="removeBlackout(' + i + ')">x</span>';
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
        endLocation: "",
        confirmed: false
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
            '<div class="leg-header"><h3>Segment ' + (i + 1) + '</h3>' +
            '<button class="btn btn-danger" onclick="removeLeg(' + i + ')">Remove</button></div>' +
            '<p style="color:#888; font-size:0.85em; margin-bottom:8px;">Click to set the date window for this segment.</p>' +
            '<div id="seg-cal-' + i + '"></div>';
        container.appendChild(card);

        var cal = new CalendarPicker("seg-cal-" + i, {
            mode: "range",
            initialYear: 2026,
            initialMonth: 8,
            rangeStart: leg.start || null,
            rangeEnd: leg.end || null,
            onSelect: (function(idx) {
                return function(range) {
                    legs[idx].start = range.start || "";
                    legs[idx].end = range.end || "";
                };
            })(i),
            onConfirm: (function(idx) {
                return function() {
                    legs[idx].confirmed = true;
                };
            })(i),
            onEdit: (function(idx) {
                return function() {
                    legs[idx].confirmed = false;
                };
            })(i)
        });
        if (leg.confirmed) {
            cal.collapsed = true;
            cal.render();
        }
    });
}

// ---------------------------------------------------------------------------
// Locations: Render per-leg location fields
// ---------------------------------------------------------------------------

function renderSegmentLocations() {
    var container = document.getElementById("segment-locations");
    if (!container) return;

    // Restore segments from sessionStorage if empty
    if (legs.length === 0) {
        var stored = sessionStorage.getItem("legs");
        if (stored) legs = JSON.parse(stored);
    }

    container.innerHTML = "";
    if (legs.length === 0) return;

    legs.forEach(function(seg, i) {
        var card = document.createElement("section");
        card.className = "card";
        var dateLabel = "";
        if (seg.start && seg.end) {
            dateLabel = " (" + formatDate(seg.start) + " to " + formatDate(seg.end) + ")";
        }
        card.innerHTML =
            '<h2>Segment ' + (i + 1) + ' Locations' + dateLabel + '</h2>' +
            '<div class="form-row">' +
            '<div class="form-group"><label>Start Location</label>' +
            '<input type="text" id="seg-start-loc-' + i + '" value="' + (seg.startLocation || '') + '" placeholder="e.g. Chicago, IL">' +
            '<button type="button" class="btn btn-secondary" style="margin-top:6px; padding:4px 12px; font-size:0.8em;" onclick="useHomeBase(\'seg-start-loc-' + i + '\')">Use Home Base</button></div>' +
            '<div class="form-group"><label>End Location</label>' +
            '<input type="text" id="seg-end-loc-' + i + '" value="' + (seg.endLocation || '') + '" placeholder="e.g. Indianapolis, IN">' +
            '<button type="button" class="btn btn-secondary" style="margin-top:6px; padding:4px 12px; font-size:0.8em;" onclick="useHomeBase(\'seg-end-loc-' + i + '\')">Use Home Base</button></div>' +
            '</div>';
        container.appendChild(card);
    });
}

function useHomeBase(inputId) {
    var homeBaseEl = document.getElementById("home-base");
    var targetEl = document.getElementById(inputId);
    if (homeBaseEl && targetEl) {
        targetEl.value = homeBaseEl.value;
    }
}

// ---------------------------------------------------------------------------
// Setup: Save Dates (step 1 — dates, legs dates, blackouts only)
// ---------------------------------------------------------------------------

function saveDates() {
    var startDate = document.getElementById("start-date").value;
    var endDate = document.getElementById("end-date").value;

    if (!startDate || !endDate) {
        showStatus("setup-status", "Please set both start and end dates.", true);
        return;
    }

    // Store dates in sessionStorage so the locations page can access them
    sessionStorage.setItem("tripStartDate", startDate);
    sessionStorage.setItem("tripEndDate", endDate);
    sessionStorage.setItem("blackoutDates", JSON.stringify(blackoutDates));
    sessionStorage.setItem("legs", JSON.stringify(legs));

    showStatus("setup-status", "Dates saved! Setting up locations...", false);
    setTimeout(function() {
        window.location.href = "/locations";
    }, 500);
}

// ---------------------------------------------------------------------------
// Locations: Save Locations (step 2 — sends full trip config to API)
// ---------------------------------------------------------------------------

function saveLocations() {
    var homeBase = document.getElementById("home-base").value;

    if (!homeBase) {
        showStatus("locations-status", "Please set a home base location.", true);
        return;
    }

    // Restore dates from sessionStorage
    var startDate = sessionStorage.getItem("tripStartDate");
    var endDate = sessionStorage.getItem("tripEndDate");
    var storedBlackouts = JSON.parse(sessionStorage.getItem("blackoutDates") || "[]");
    var storedSegments = JSON.parse(sessionStorage.getItem("legs") || "[]");

    // Update segment locations from the form inputs
    storedSegments.forEach(function(seg, i) {
        var startEl = document.getElementById("seg-start-loc-" + i);
        var endEl = document.getElementById("seg-end-loc-" + i);
        if (startEl) seg.startLocation = startEl.value;
        if (endEl) seg.endLocation = endEl.value;
    });

    var tripData = {
        date_range: { start: startDate, end: endDate },
        home_base: homeBase,
        blackout_dates: storedBlackouts,
        segments: storedSegments.map(function(s) {
            return {
                date_range: { start: s.start, end: s.end },
                start_location: s.startLocation || homeBase,
                end_location: s.endLocation || homeBase
            };
        })
    };

    fetch("/api/trip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tripData)
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.status === "ok") {
            showStatus("locations-status", "Locations saved! Proceeding to attractions...", false);
            setTimeout(function() {
                window.location.href = "/attractions";
            }, 800);
        } else {
            showStatus("locations-status", "Error: " + JSON.stringify(data), true);
        }
    })
    .catch(function(err) {
        showStatus("locations-status", "Network error: " + err.message, true);
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

function importCSV() {
    var fileInput = document.getElementById("csv-file");
    if (!fileInput || !fileInput.files.length) {
        showStatus("csv-status", "Please select a CSV file.", true);
        return;
    }

    var reader = new FileReader();
    reader.onload = function(e) {
        var text = e.target.result;
        var lines = text.split(/\r?\n/).filter(function(l) { return l.trim(); });
        if (lines.length < 2) {
            showStatus("csv-status", "CSV must have a header row and at least one data row.", true);
            return;
        }

        var header = lines[0].toLowerCase();
        var hasScheduledDate = header.indexOf("scheduled") !== -1 || header.split(",").length >= 4;
        var added = 0;
        var errors = [];
        var pending = [];

        for (var i = 1; i < lines.length; i++) {
            var cols = parseCSVLine(lines[i]);
            if (cols.length < 3) {
                errors.push("Row " + (i + 1) + ": needs at least 3 columns");
                continue;
            }

            var name = cols[0].trim();
            var address = cols[1].trim();
            var url = cols[2].trim();
            var assignedDates = [];

            if (cols.length >= 4 && cols[3].trim()) {
                assignedDates = cols[3].split(/[,;]/).map(function(d) { return d.trim(); }).filter(function(d) { return d; });
            }

            if (!name || !address) {
                errors.push("Row " + (i + 1) + ": name and address are required");
                continue;
            }

            pending.push({ name: name, address: address, schedule_url: url, assigned_dates: assignedDates });
        }

        if (pending.length === 0) {
            showStatus("csv-status", "No valid rows found. " + errors.join("; "), true);
            return;
        }

        showStatus("csv-status", "Importing " + pending.length + " attractions...", false);

        var chain = Promise.resolve();
        pending.forEach(function(attrData) {
            chain = chain.then(function() {
                return fetch("/api/attractions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(attrData)
                }).then(function(resp) { return resp.json(); }).then(function(data) {
                    if (data.status === "ok") {
                        attractions.push({ name: attrData.name, address: attrData.address, url: attrData.schedule_url });
                        added++;
                    }
                });
            });
        });

        chain.then(function() {
            renderAttractions();
            var msg = "Imported " + added + " attraction" + (added !== 1 ? "s" : "");
            if (errors.length) msg += ". Skipped: " + errors.join("; ");
            showStatus("csv-status", msg, errors.length > 0);
            fileInput.value = "";
        });
    };

    reader.readAsText(fileInput.files[0]);
}

function parseCSVLine(line) {
    var result = [];
    var current = "";
    var inQuotes = false;
    for (var i = 0; i < line.length; i++) {
        var ch = line[i];
        if (ch === '"') {
            inQuotes = !inQuotes;
        } else if (ch === ',' && !inQuotes) {
            result.push(current);
            current = "";
        } else {
            current += ch;
        }
    }
    result.push(current);
    return result;
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
            '<th>Date</th><th>Open</th><th>Close</th><th>Price ($)</th><th>Ticket URL</th>' +
            '</tr></thead><tbody>';

        var dates = result.dates || [];
        var times = result.time_ranges || [];
        var prices = result.prices || [];
        var ticketUrls = result.ticket_urls || [];

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
        table += '<button type="button" class="btn btn-secondary" style="margin-top:8px; font-size:0.85em;" onclick="addReviewRow(' + idx + ')">+ Add Date</button>';

        card.innerHTML = header + table;
        container.appendChild(card);
    });

    var btn = document.getElementById("generate-btn");
    if (btn) btn.disabled = false;
}

function importScheduleCSV() {
    var fileInput = document.getElementById("schedule-csv-file");
    if (!fileInput || !fileInput.files.length) {
        showStatus("schedule-csv-status", "Please select a CSV file.", true);
        return;
    }

    var reader = new FileReader();
    reader.onload = function(e) {
        var text = e.target.result;
        var lines = text.split(/\r?\n/).filter(function(l) { return l.trim(); });
        if (lines.length < 2) {
            showStatus("schedule-csv-status", "CSV must have a header row and at least one data row.", true);
            return;
        }

        // Group schedule entries by attraction name
        var byName = {};
        for (var i = 1; i < lines.length; i++) {
            var cols = parseCSVLine(lines[i]);
            if (cols.length < 4) continue;

            var name = cols[0].trim();
            var dateVal = cols[1].trim();
            var openVal = cols[2].trim() || "19:00";
            var closeVal = cols[3].trim() || "23:00";
            var price = cols.length >= 5 && cols[4].trim() ? parseFloat(cols[4].trim()) : null;
            var ticketUrl = cols.length >= 6 ? cols[5].trim() || null : null;

            if (!name || !dateVal) continue;

            if (!byName[name]) byName[name] = [];
            byName[name].push({
                date: dateVal,
                open_time: openVal,
                close_time: closeVal,
                price: price,
                ticket_url: ticketUrl
            });
        }

        var names = Object.keys(byName);
        if (names.length === 0) {
            showStatus("schedule-csv-status", "No valid schedule rows found.", true);
            return;
        }

        showStatus("schedule-csv-status", "Importing schedules for " + names.length + " attraction(s)...", false);

        var chain = Promise.resolve();
        names.forEach(function(name) {
            chain = chain.then(function() {
                return fetch("/api/schedule", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: name, schedule: byName[name] })
                }).then(function(resp) { return resp.json(); });
            });
        });

        chain.then(function() {
            showStatus("schedule-csv-status", "Imported schedules for " + names.length + " attraction(s). Refreshing...", false);
            // Update scrapedResults to reflect imported data
            names.forEach(function(name) {
                var existing = scrapedResults.find(function(r) { return r.name === name; });
                if (existing) {
                    existing.dates = byName[name].map(function(e) { return e.date; });
                    existing.time_ranges = [[byName[name][0].open_time, byName[name][0].close_time]];
                    existing.prices = byName[name][0].price != null ? [byName[name][0].price] : [];
                    existing.ticket_urls = byName[name][0].ticket_url ? [byName[name][0].ticket_url] : [];
                    existing.confidence = "green";
                }
            });
            renderReview();
            fileInput.value = "";
        });
    };

    reader.readAsText(fileInput.files[0]);
}

function addReviewRow(attrIdx) {
    var card = document.querySelectorAll(".review-card")[attrIdx];
    if (!card) return;
    var tbody = card.querySelector("tbody");
    if (!tbody) return;

    var emptyRow = tbody.querySelector('td[colspan]');
    if (emptyRow) emptyRow.parentElement.remove();

    var rowCount = tbody.querySelectorAll("tr").length;
    var tr = document.createElement("tr");
    tr.innerHTML =
        '<td><input type="date" value="" data-attr="' + attrIdx + '" data-row="' + rowCount + '" data-field="date"></td>' +
        '<td><input type="time" value="19:00" data-attr="' + attrIdx + '" data-row="' + rowCount + '" data-field="open"></td>' +
        '<td><input type="time" value="23:00" data-attr="' + attrIdx + '" data-row="' + rowCount + '" data-field="close"></td>' +
        '<td><input type="number" value="" data-attr="' + attrIdx + '" data-row="' + rowCount + '" data-field="price" step="0.01"></td>' +
        '<td><input type="url" value="" data-attr="' + attrIdx + '" data-row="' + rowCount + '" data-field="ticket" placeholder="https://..."></td>';
    tbody.appendChild(tr);
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
        var parts = d.split("-");
        header.textContent = MONTH_NAMES[parseInt(parts[1], 10) - 1] + " " + parseInt(parts[2], 10);
        container.appendChild(header);

        var nightlyTotal = 0;
        scheduled[d].forEach(function(entry) {
            var div = document.createElement("div");
            div.className = "haunt-entry";

            var priceVal = (entry.price !== null && entry.price !== undefined) ? entry.price : 0;
            nightlyTotal += priceVal;
            var entryDate = d;
            var entryName = entry.name;
            var ticketHtml = entry.ticket_url
                ? ' &mdash; <a href="' + entry.ticket_url + '" target="_blank">Buy Tickets</a>'
                : '';
            var priceHtml = '<div class="haunt-price">' +
                '$<input type="number" class="inline-price" value="' + (priceVal || '') + '" step="0.01" min="0" ' +
                'data-name="' + entryName.replace(/"/g, '&quot;') + '" data-date="' + entryDate + '" ' +
                'onchange="updatePrice(this)">' +
                ticketHtml + '</div>';

            var driveHtml = "";
            if (entry.drive_time_min != null) {
                var hrs = Math.floor(entry.drive_time_min / 60);
                var mins = entry.drive_time_min % 60;
                var driveLabel = hrs > 0 ? hrs + "h " + mins + "m" : mins + "m";
                driveHtml = ' <span class="haunt-drive">(' + driveLabel + ' drive)</span>';
            }

            var durationVal = entry.duration_min || 45;
            var durationHtml = '<div class="haunt-duration">' +
                'Est. time: <input type="number" class="inline-duration" value="' + durationVal + '" min="10" max="180" step="5" ' +
                'data-name="' + entryName.replace(/"/g, '&quot;') + '" ' +
                'onchange="updateDuration(this)"> min</div>';

            div.innerHTML =
                '<div class="haunt-name">' + entry.name + '</div>' +
                '<div class="haunt-time">Arrive: ' + formatTime(entry.arrival_time) +
                driveHtml +
                ' | Open: ' + formatTime(entry.open_time) +
                ' - ' + formatTime(entry.close_time) + '</div>' +
                priceHtml +
                durationHtml;

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

    // Unscheduled (collapsed by default, grouped by reason)
    if (unscheduled.length > 0) {
        var section = document.createElement("div");
        section.className = "unscheduled-section";

        var toggle = document.createElement("div");
        toggle.className = "unscheduled-toggle";
        toggle.innerHTML = '<span class="unscheduled-arrow">&#9654;</span> ' +
            '<strong>Could Not Schedule</strong> (' + unscheduled.length +
            ' haunt' + (unscheduled.length !== 1 ? 's' : '') + ')';
        toggle.style.cursor = "pointer";

        var details = document.createElement("div");
        details.className = "unscheduled-details";
        details.style.display = "none";

        // Group by reason
        var byReason = {};
        unscheduled.forEach(function(item) {
            var r = item.reason || "Unknown reason";
            if (!byReason[r]) byReason[r] = [];
            byReason[r].push(item.name);
        });

        Object.keys(byReason).forEach(function(reason) {
            var group = document.createElement("div");
            group.style.marginBottom = "8px";
            group.innerHTML = '<div style="color:#e74c3c; font-size:0.85em; margin-bottom:2px;">' + reason + '</div>' +
                '<div style="color:#aaa; font-size:0.85em;">' + byReason[reason].join(", ") + '</div>';
            details.appendChild(group);
        });

        toggle.onclick = function() {
            var showing = details.style.display !== "none";
            details.style.display = showing ? "none" : "block";
            toggle.querySelector(".unscheduled-arrow").innerHTML = showing ? "&#9654;" : "&#9660;";
        };

        section.appendChild(toggle);
        section.appendChild(details);
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

            var suggestions = data.suggestions || [];
            if (suggestions.length === 0) return;

            panel.style.display = "block";
            content.innerHTML = "";

            suggestions.forEach(function(s, i) {
                var div = document.createElement("div");
                div.className = "suggestion";
                var dateLabel = s.date ? formatDate(s.date) : "";
                div.innerHTML =
                    '<label style="display:flex; align-items:flex-start; gap:10px; cursor:pointer; margin:0;">' +
                    '<input type="checkbox" class="suggestion-check" data-idx="' + i + '" style="margin-top:4px;">' +
                    '<div>' +
                    '<div class="suggestion-name">' + s.name + '</div>' +
                    '<div class="suggestion-detail">' +
                    (dateLabel ? "Suggested: " + dateLabel + " | " : "") +
                    s.distance + " mi away | " +
                    s.type.replace("_", " ") +
                    '</div>' +
                    (s.url ? '<a href="' + s.url + '" target="_blank" onclick="event.stopPropagation()">View Website</a>' : "") +
                    '</div></label>';
                content.appendChild(div);
            });

            // Store suggestions for later use
            window._discoverySuggestions = suggestions;

            var btnRow = document.createElement("div");
            btnRow.style.marginTop = "12px";
            btnRow.innerHTML = '<button class="btn btn-primary" onclick="addSelectedSuggestions()">Add Selected to Itinerary</button>';
            content.appendChild(btnRow);
        })
        .catch(function() {
            // Silently fail for discovery
        });
}

function addSelectedSuggestions() {
    var checks = document.querySelectorAll(".suggestion-check:checked");
    if (checks.length === 0) return;

    var suggestions = window._discoverySuggestions || [];
    var toAdd = [];
    checks.forEach(function(cb) {
        var idx = parseInt(cb.getAttribute("data-idx"), 10);
        if (suggestions[idx]) toAdd.push(suggestions[idx]);
    });

    if (toAdd.length === 0) return;

    var chain = Promise.resolve();
    toAdd.forEach(function(s) {
        chain = chain.then(function() {
            return fetch("/api/attractions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: s.name,
                    address: s.address || "",
                    schedule_url: s.url || "",
                    assigned_dates: s.date ? [s.date] : []
                })
            });
        });
    });

    chain.then(function() {
        return fetch("/api/optimize", { method: "POST" });
    }).then(function(resp) {
        return resp.json();
    }).then(function(data) {
        renderItinerary(data);
        loadDiscoverySuggestions();
    });
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

function updateDuration(input) {
    var name = input.getAttribute("data-name");
    var newDuration = input.value ? parseInt(input.value) : 45;

    fetch("/api/duration", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ name: name, duration_min: newDuration })
    }).then(function(resp) {
        return resp.json();
    }).then(function(data) {
        if (data.scheduled) {
            renderItinerary(data);
        }
    });
}

function updatePrice(input) {
    var name = input.getAttribute("data-name");
    var entryDate = input.getAttribute("data-date");
    var newPrice = input.value ? parseFloat(input.value) : null;

    fetch("/api/price", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ name: name, date: entryDate, price: newPrice })
    }).then(function(resp) {
        if (!resp.ok) return;
        recalcTotals();
    });
}

function recalcTotals() {
    var container = document.getElementById("itinerary-container");
    if (!container) return;

    var tripTotal = 0;
    container.querySelectorAll(".date-header").forEach(function(header) {
        var nightlyTotal = 0;
        var sibling = header.nextElementSibling;
        while (sibling && !sibling.classList.contains("date-header") && !sibling.classList.contains("subtotal") && !sibling.classList.contains("trip-total") && !sibling.classList.contains("unscheduled-section")) {
            var priceInput = sibling.querySelector(".inline-price");
            if (priceInput && priceInput.value) {
                nightlyTotal += parseFloat(priceInput.value) || 0;
            }
            sibling = sibling.nextElementSibling;
        }
        if (sibling && sibling.classList.contains("subtotal")) {
            sibling.textContent = "Nightly Total: $" + nightlyTotal.toFixed(2);
        }
        tripTotal += nightlyTotal;
    });

    var totalEl = container.querySelector(".trip-total");
    if (totalEl) {
        totalEl.textContent = "Trip Total: $" + tripTotal.toFixed(2);
    }
}

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
