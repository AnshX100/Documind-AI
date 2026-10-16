/**
 * FinPilot AI Dashboard Client Library
 * Handles:
 * - requestAnimationFrame() smooth number counting transitions
 * - Pure SVG trend chart rendering and line stroke draw animations
 * - AJAX date range filters and category progress bar transitions
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Formatters
    const formatCurrency = (val) => {
        const num = Math.round(val || 0);
        const str = num.toString();
        const lastThree = str.substring(str.length - 3);
        const otherNumbers = str.substring(0, str.length - 3);
        const formattedThree = otherNumbers !== '' ? ',' + lastThree : lastThree;
        return '₹' + otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + formattedThree;
    };

    const formatInteger = (val) => {
        return Math.round(val || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    };

    const formatPercentage = (val) => {
        return Math.round(val || 0).toString() + '%';
    };

    // 2. Animate Number Counter (with frame cancel tracking to prevent flicker race conditions)
    const activeAnimations = {};

    const animateNumber = (elementId, targetValue, duration = 1200, formatter = formatInteger) => {
        const el = document.getElementById(elementId);
        if (!el) return;

        const numericTarget = parseFloat(targetValue) || 0;

        // Cancel existing animation loop on this element
        if (activeAnimations[elementId]) {
            cancelAnimationFrame(activeAnimations[elementId]);
        }

        // Respect reduced motion settings (browser-wide or session settings)
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches || 
                                     document.documentElement.getAttribute('data-reduced-motion') === 'true';
        
        if (prefersReducedMotion) {
            el.textContent = formatter(numericTarget);
            return;
        }

        const startValue = 0;
        const startTime = performance.now();

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function (outCubic)
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = startValue + ease * (numericTarget - startValue);

            el.textContent = formatter(current);

            if (progress < 1) {
                activeAnimations[elementId] = requestAnimationFrame(update);
            } else {
                el.textContent = formatter(numericTarget);
                delete activeAnimations[elementId];
            }
        };

        activeAnimations[elementId] = requestAnimationFrame(update);
    };

    // 3. Dynamic SVG Chart Drawing & Animation
    const drawTrendChart = (monthlyTrend) => {
        const line = document.getElementById('trendChartLine');
        const area = document.getElementById('trendChartArea');
        if (!line || !area || !monthlyTrend || monthlyTrend.length === 0) return;

        const width = 650;
        const height = 225;
        const n = monthlyTrend.length;
        const xStep = n > 1 ? width / (n - 1) : width;

        // Get max total value
        const totals = monthlyTrend.map(pt => parseFloat(pt.total || 0));
        const maxVal = Math.max(...totals, 1);

        // Map coordinates
        const points = monthlyTrend.map((pt, i) => {
            const x = i * xStep;
            // Leave a 20px padding at top and 15px at bottom of 225px box
            const y = height - (parseFloat(pt.total || 0) / maxVal) * 180 - 20;
            return { x, y };
        });

        // 1. Build Polyline Points
        const polylinePoints = points.map(pt => `${pt.x},${pt.y}`).join(' ');
        line.setAttribute('points', polylinePoints);

        // 2. Build Path Fill Area
        const pathD = `M 0 ${points[0].y} ` + 
                      points.map((pt, i) => i > 0 ? `L ${pt.x} ${pt.y}` : '').join(' ') + 
                      ` L ${width} ${height} L 0 ${height} Z`;
        area.setAttribute('d', pathD);

        // 3. Line Draw Animation (stroke-dashoffset)
        const length = line.getTotalLength ? line.getTotalLength() : 1000;
        line.style.strokeDasharray = length;
        line.style.strokeDashoffset = length;
        line.style.transition = 'none';
        
        // Force Reflow
        line.getBoundingClientRect();
        
        line.style.transition = 'stroke-dashoffset 1.4s cubic-bezier(0.4, 0, 0.2, 1)';
        line.style.strokeDashoffset = '0';

        // 4. Fill Area Left-to-Right Slide (clip-path animation)
        area.style.clipPath = 'polygon(0 0, 0 0, 0 100%, 0 100%)';
        area.style.transition = 'none';
        
        // Force Reflow
        area.getBoundingClientRect();
        
        area.style.transition = 'clip-path 1.4s cubic-bezier(0.4, 0, 0.2, 1)';
        area.style.clipPath = 'polygon(0 0, 100% 0, 100% 100%, 0 100%)';
    };

    // 4. Animate Category Bars Widths
    const animateCategoryBars = () => {
        document.querySelectorAll('.bartrack i').forEach(bar => {
            const targetWidth = bar.getAttribute('data-width') || '0';
            bar.style.width = '0%';
            bar.getBoundingClientRect();
            bar.style.transition = 'width 1.2s cubic-bezier(0.4, 0, 0.2, 1)';
            bar.style.width = targetWidth + '%';
        });
    };

    // 5. Initialize from pre-loaded Jinja block
    const initialDataEl = document.getElementById('initialDashboardData');
    if (initialDataEl) {
        try {
            const data = JSON.parse(initialDataEl.textContent);
            if (data && data.metrics) {
                // Animate counters
                if (document.getElementById('valTotalExpenses')) {
                    animateNumber('valTotalExpenses', data.metrics.total_expenses, 1200, formatCurrency);
                }
                if (document.getElementById('valAvgTransaction')) {
                    animateNumber('valAvgTransaction', data.metrics.average_expense, 1200, formatCurrency);
                }
                if (document.getElementById('valTotalDocs')) {
                    animateNumber('valTotalDocs', data.metrics.total_documents, 1000, formatInteger);
                }
                if (document.getElementById('valPendingDocs')) {
                    animateNumber('valPendingDocs', data.metrics.pending_documents, 1000, formatInteger);
                }
                if (document.getElementById('valRiskSignals')) {
                    const el = document.getElementById('valRiskSignals');
                    const target = el.getAttribute('data-value') || data.metrics.high_risk_anomalies || 0;
                    animateNumber('valRiskSignals', target, 1000, formatInteger);
                }
                
                // Animate DD Score if present
                const scoreVal = document.getElementById('valDdScore');
                if (scoreVal) {
                    const targetScore = parseInt(scoreVal.getAttribute('data-value') || '100');
                    animateNumber('valDdScore', targetScore, 1400, (v) => `${Math.round(v)}/100`);
                }

                // Render and animate graph
                if (data.monthly_trend && data.monthly_trend.length > 0) {
                    drawTrendChart(data.monthly_trend);
                }
                
                // Animate category progress bars
                animateCategoryBars();
            }
        } catch (e) {
            console.error("Failed to parse initial dashboard data", e);
        }
    }

    // 6. Handle Range Filter AJAX Updates
    const filterEl = document.getElementById('dateRangeFilter');
    if (filterEl) {
        filterEl.addEventListener('change', async (e) => {
            const selectedRange = e.target.value;
            try {
                // Fetch dynamic dashboard range data
                const res = await fetch(`/dashboard/api/data?range=${selectedRange}`);
                const data = await res.json();
                
                if (data && data.metrics) {
                    // Re-trigger counters
                    if (document.getElementById('valTotalExpenses')) {
                        animateNumber('valTotalExpenses', data.metrics.total_expenses, 1000, formatCurrency);
                    }
                    if (document.getElementById('valAvgTransaction')) {
                        animateNumber('valAvgTransaction', data.metrics.average_expense, 1000, formatCurrency);
                    }
                    if (document.getElementById('valTotalDocs')) {
                        animateNumber('valTotalDocs', data.metrics.total_documents, 800, formatInteger);
                    }
                    if (document.getElementById('valPendingDocs')) {
                        animateNumber('valPendingDocs', data.metrics.pending_documents, 800, formatInteger);
                    }
                    if (document.getElementById('valRiskSignals')) {
                        const target = data.metrics.high_risk_anomalies || 0;
                        animateNumber('valRiskSignals', target, 800, formatInteger);
                    }
                    
                    // Recalculate DD Score dynamically on filter change
                    const totalDocs = data.metrics.total_documents || 0;
                    const pendingDocs = data.metrics.pending_documents || 0;
                    const failedDocs = data.metrics.failed_documents || 0;
                    let ddScore = 100;
                    if (totalDocs > 0) {
                        ddScore = Math.max(30, Math.round(100 - (pendingDocs / totalDocs) * 40 - (failedDocs / totalDocs) * 60));
                    }
                    if (document.getElementById('valDdScore')) {
                        animateNumber('valDdScore', ddScore, 1000, (v) => `${Math.round(v)}/100`);
                    }

                    // Re-draw categories list in sidebar card
                    const catContainer = document.getElementById('categoryContainer');
                    if (catContainer && data.category_breakdown) {
                        if (data.category_breakdown.length === 0) {
                            catContainer.innerHTML = '<p style="color: var(--muted); font-size: 13px; padding: 20px 0; text-align: center;">No category statistics found.</p>';
                        } else {
                            const maxVal = Math.max(...data.category_breakdown.map(c => c.total), 1);
                            catContainer.innerHTML = data.category_breakdown.map(cat => {
                                const percent = Math.round((cat.total / maxVal) * 100);
                                return `
                                    <div class="bar">
                                        <span style="font-weight: 500; font-size: 12px; color: var(--ink);">${cat.category}</span>
                                        <div class="bartrack"><i data-width="${percent}" style="width: 0%;"></i></div>
                                        <b>₹${cat.total.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</b>
                                    </div>
                                `;
                            }).join('');
                            // Animate new category progress bars
                            animateCategoryBars();
                        }
                    }

                    // Redraw graph
                    if (data.monthly_trend) {
                        drawTrendChart(data.monthly_trend);
                    }
                }
            } catch (err) {
                console.error("Failed to load dashboard data via AJAX", err);
            }
        });
    }
});
