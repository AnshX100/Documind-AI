/**
 * DocuMind AI Document Workspace Viewer (PDF/Image/DOCX)
 * Handles zoom, pagination, loading states, and viewport boundary checks.
 */
document.addEventListener('DOMContentLoaded', () => {
    const configEl = document.getElementById('viewerConfig');
    if (!configEl) return;

    const isPdf = configEl.getAttribute('data-is-pdf') === 'true';
    const isImage = configEl.getAttribute('data-is-image') === 'true';
    const isDocx = configEl.getAttribute('data-is-docx') === 'true';
    const previewUrl = configEl.getAttribute('data-preview-url');

    const wrapper = document.getElementById('documentCanvasWrapper');
    const container = document.getElementById('viewerContainer');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const errorOverlay = document.getElementById('errorOverlay');

    let scale = 1.0;

    // Helper: Safely toggle loading/error overlays using inline display properties
    const setOverlayState = (loading, error) => {
        if (loadingOverlay) loadingOverlay.style.display = loading ? 'flex' : 'none';
        if (errorOverlay) errorOverlay.style.display = error ? 'flex' : 'none';
    };

    // Initial state: loading active, error hidden
    setOverlayState(true, false);

    if (isPdf) {
        // 1. PDF.js Viewer Engine
        if (typeof pdfjsLib === 'undefined') {
            console.error("PDF.js library is not loaded.");
            setOverlayState(false, true);
            return;
        }

        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        
        let pdfDoc = null,
            pageNum = 1,
            pageRendering = false,
            pageNumPending = null,
            canvas = document.getElementById('pdfCanvas'),
            ctx = canvas.getContext('2d');

        const renderPage = (num) => {
            pageRendering = true;
            
            pdfDoc.getPage(num).then((page) => {
                let viewport = page.getViewport({ scale: scale });
                
                // Limit maximum width to prevent massive canvas crashes
                if (viewport.width > 2800) {
                    scale = 2800 / page.getViewport({ scale: 1.0 }).width;
                    viewport = page.getViewport({ scale: scale });
                }
                
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                
                // Physically size the wrapper in pixels to trigger viewport overflow scrollbars
                if (wrapper) {
                    wrapper.style.width = viewport.width + 'px';
                    wrapper.style.height = viewport.height + 'px';
                }
                
                const renderContext = {
                    canvasContext: ctx,
                    viewport: viewport
                };
                
                const renderTask = page.render(renderContext);
                renderTask.promise.then(() => {
                    pageRendering = false;
                    setOverlayState(false, false); // Successfully rendered
                    updateZoomText();
                    updateButtonStates();
                    
                    if (pageNumPending !== null) {
                        renderPage(pageNumPending);
                        pageNumPending = null;
                    }
                }).catch((err) => {
                    console.error("PDF render task error:", err);
                    pageRendering = false;
                    setOverlayState(false, true);
                });
            }).catch((err) => {
                console.error("PDF getPage error:", err);
                pageRendering = false;
                setOverlayState(false, true);
            });
            
            const numEl = document.getElementById('pageNum');
            if (numEl) numEl.textContent = num;
        };

        const queueRenderPage = (num) => {
            if (pageRendering) {
                pageNumPending = num;
            } else {
                renderPage(num);
            }
        };

        const onPrevPage = () => {
            if (pageNum <= 1) return;
            pageNum--;
            queueRenderPage(pageNum);
        };
        
        const onNextPage = () => {
            if (pageNum >= pdfDoc.numPages) return;
            pageNum++;
            queueRenderPage(pageNum);
        };
        
        const updateButtonStates = () => {
            const prevBtn = document.getElementById('prevPage');
            const nextBtn = document.getElementById('nextPage');
            if (prevBtn) prevBtn.disabled = (pageNum <= 1);
            if (nextBtn) nextBtn.disabled = (pageNum >= pdfDoc.numPages);
        };
        
        const updateZoomText = () => {
            const levelEl = document.getElementById('zoomLevel');
            if (levelEl) levelEl.textContent = Math.round(scale * 100) + '%';
        };
        
        const onZoomIn = () => {
            scale = Math.min(scale + 0.25, 3.0);
            queueRenderPage(pageNum);
        };
        
        const onZoomOut = () => {
            scale = Math.max(scale - 0.25, 0.5);
            queueRenderPage(pageNum);
        };

        // Attach event triggers
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');
        const inBtn = document.getElementById('zoomIn');
        const outBtn = document.getElementById('zoomOut');

        if (prevBtn) prevBtn.addEventListener('click', onPrevPage);
        if (nextBtn) nextBtn.addEventListener('click', onNextPage);
        if (inBtn) inBtn.addEventListener('click', onZoomIn);
        if (outBtn) outBtn.addEventListener('click', onZoomOut);
        
        // Navigation keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') onPrevPage();
            else if (e.key === 'ArrowRight') onNextPage();
        });

        // Load document
        pdfjsLib.getDocument(previewUrl).promise.then((pdfDoc_) => {
            pdfDoc = pdfDoc_;
            const countEl = document.getElementById('pageCount');
            if (countEl) countEl.textContent = pdfDoc.numPages;
            
            pdfDoc.getPage(1).then((page) => {
                const unscaledViewport = page.getViewport({ scale: 1.0 });
                const containerWidth = container.clientWidth - 40; 
                // Auto-fit to viewport width on first load
                if (unscaledViewport.width > containerWidth) {
                    scale = containerWidth / unscaledViewport.width;
                }
                renderPage(pageNum);
            }).catch((err) => {
                console.error("PDF load first page error:", err);
                setOverlayState(false, true);
            });
        }).catch((err) => {
            console.error('PDF loading task error:', err);
            setOverlayState(false, true);
        });

    } else if (isImage || isDocx) {
        // 2. Image / DOCX Viewer Engine
        const updateTransform = () => {
            const img = document.getElementById('imagePreview');
            if (img) {
                const baseWidth = img.naturalWidth || 600;
                // Physically scale image width to trigger container scrollbars
                img.style.width = (baseWidth * scale) + 'px';
                img.style.height = 'auto';
            }
            
            const docx = document.getElementById('docxPreview');
            if (docx) {
                docx.style.transform = `scale(${scale})`;
                docx.style.transformOrigin = 'top center';
                // Adjust docx wrapper width physically to allow scrolling
                if (wrapper) {
                    wrapper.style.width = (800 * scale) + 'px';
                }
            }
            
            const levelEl = document.getElementById('zoomLevel');
            if (levelEl) levelEl.textContent = Math.round(scale * 100) + '%';
        };

        const inBtn = document.getElementById('zoomIn');
        const outBtn = document.getElementById('zoomOut');

        if (inBtn) {
            inBtn.addEventListener('click', () => {
                scale = Math.min(scale + 0.25, 3.0);
                updateTransform();
            });
        }
        
        if (outBtn) {
            outBtn.addEventListener('click', () => {
                scale = Math.max(scale - 0.25, 0.25);
                updateTransform();
            });
        }

        // Hide overlay once loading completes (triggered on window load or img onload)
        const img = document.getElementById('imagePreview');
        if (img) {
            if (img.complete) {
                setOverlayState(false, false);
            } else {
                img.onload = () => setOverlayState(false, false);
                img.onerror = () => setOverlayState(false, true);
            }
        } else if (isDocx) {
            setOverlayState(false, false);
        } else {
            setOverlayState(false, true);
        }
    } else {
        // Fallback for unsupported formats
        setOverlayState(false, true);
    }
});
