'use client';

import { createContext, useContext } from 'react';

interface MockContextValue {
  isMock: boolean;
}

const MockContext = createContext<MockContextValue>({ isMock: false });

export function MockProvider({ children }: { children: React.ReactNode }) {
  return (
    <MockContext.Provider value={{ isMock: true }}>
      {children}
    </MockContext.Provider>
  );
}

export function useMock(): MockContextValue {
  return useContext(MockContext);
}
