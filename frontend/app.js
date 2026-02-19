/**
 * MAARS app - main entry point, wires modules together.
 */
(function () {
    'use strict';

    function debounce(fn, ms) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    document.addEventListener('DOMContentLoaded', () => {
        const cfg = window.MAARS?.config;
        const theme = window.MAARS?.theme;
        const planner = window.MAARS?.planner;
        const monitor = window.MAARS?.monitor;
        const ws = window.MAARS?.ws;

        if (theme) {
            theme.initTheme();
            document.getElementById('themeToggleBtn')?.addEventListener('click', theme.toggleTheme);
            theme.initApiConfigModal();
        }
        if (cfg && cfg.resolvePlanId) cfg.resolvePlanId().catch(() => {});
        if (planner) planner.init();
        if (monitor) monitor.init();
        if (ws) ws.init();

        if (typeof TaskTree !== 'undefined' && TaskTree.initClickHandlers) {
            TaskTree.initClickHandlers();
        }
    });

    window.addEventListener('resize', debounce(() => {
        const diagramContent = document.getElementById('diagramArea');
        if (!diagramContent) return;
        const timetableWrapper = diagramContent.querySelector('.timetable-wrapper');
        if (!timetableWrapper) return;
        const monitor = window.MAARS?.monitor;
        if (!monitor) return;
        const { cellSize: fixedCellSize, rightAreaWidth } = monitor.calculateFixedCellSize(timetableWrapper);
        const rightArea = diagramContent.querySelector('.timetable-right');
        if (rightArea) {
            rightArea.style.width = rightArea.style.minWidth = rightArea.style.maxWidth = `${rightAreaWidth}px`;
        }
        const leftHeader = diagramContent.querySelector('.timetable-left-header');
        const leftGrid = diagramContent.querySelector('.timetable-left-grid');
        const rightHeader = diagramContent.querySelector('.timetable-right-header');
        const rightGrid = diagramContent.querySelector('.timetable-right-grid');
        const gap = 1;
        if (leftHeader && leftGrid) {
            const actualCols = parseInt(leftGrid.getAttribute('data-cols')) || 10;
            const actualRows = parseInt(leftGrid.getAttribute('data-rows')) || 4;
            const w = actualCols * fixedCellSize + gap * (actualCols - 1);
            const h = actualRows * fixedCellSize + gap * (actualRows - 1);
            leftHeader.style.gridTemplateColumns = leftGrid.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${actualRows}, ${fixedCellSize}px)`;
            leftGrid.style.width = leftGrid.style.minWidth = leftHeader.style.width = leftHeader.style.minWidth = `${w}px`;
            leftGrid.style.height = leftGrid.style.minHeight = `${h}px`;
        }
        if (rightHeader && rightGrid) {
            const rightCols = parseInt(rightGrid.getAttribute('data-cols')) || 3;
            const rightRows = parseInt(rightGrid.getAttribute('data-rows')) || 4;
            const w = rightCols * fixedCellSize + gap * (rightCols - 1);
            const h = rightRows * fixedCellSize + gap * (rightRows - 1);
            rightHeader.style.gridTemplateColumns = rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
            rightGrid.style.gridTemplateRows = `repeat(${rightRows}, ${fixedCellSize}px)`;
            rightGrid.style.width = rightGrid.style.minWidth = rightHeader.style.width = rightHeader.style.minWidth = `${w}px`;
            rightGrid.style.height = rightGrid.style.minHeight = `${h}px`;
        }
        const layout = window.MAARS?.state?.timetableLayout;
        if (layout?.treeData?.length) TaskTree.renderMonitorTasksTree(layout.treeData);
    }, 150));
})();
