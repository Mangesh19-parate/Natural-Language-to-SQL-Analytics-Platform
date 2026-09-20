import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api.js';

const DataSourceContext = createContext(null);

export function DataSourceProvider({ children }) {
  const [dataSources, setDataSources] = useState([
    { data_source_id: 1, name: 'PostgreSQL Primary', db_type: 'postgresql' }
  ]);
  const [selectedDataSourceId, setSelectedDataSourceId] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  const refreshDataSources = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiFetch('/api/schema/data-sources');
      const resData = await res.json();
      if (resData?.success && Array.isArray(resData.data) && resData.data.length > 0) {
        setDataSources(resData.data);
      }
    } catch (err) {
      // Fallback to default
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshDataSources();
  }, [refreshDataSources]);

  const selectedDataSource = dataSources.find((ds) => ds.data_source_id === selectedDataSourceId) || dataSources[0];

  const value = {
    dataSources,
    selectedDataSourceId,
    setSelectedDataSourceId,
    selectedDataSource,
    refreshDataSources,
    isLoading,
  };

  return <DataSourceContext.Provider value={value}>{children}</DataSourceContext.Provider>;
}

export function useDataSource() {
  const context = useContext(DataSourceContext);
  if (!context) {
    throw new Error('useDataSource must be used within a DataSourceProvider');
  }
  return context;
}
