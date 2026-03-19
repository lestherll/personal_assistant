import "@testing-library/jest-dom";

// Silence React warnings about act() in tests
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
