import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api.js';

const DataSourceContext = createContext(null);

export function DataSourceProvider({ children }) {
  const [dataSources, setDataSources] = useState([]);
  const [selectedDataSourceId, setSelectedDataSourceId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshDataSources = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiFetch('/api/schema/data-sources');
      const resData = await res.json();
      if (resData?.success && Array.isArray(resData.data) && resData.data.length > 0) {
        setDataSources(resData.data);
        setSelectedDataSourceId((prev) => {
          if (prev && resData.data.some((ds) => ds.data_source_id === prev)) {
            return prev;
          }
          return resData.data[0].data_source_id;
        });
      } else {
        setDataSources([]);
        setSelectedDataSourceId(null);
      }
    } catch (err) {
      setDataSources([]);
      setSelectedDataSourceId(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshDataSources();
  }, [refreshDataSources]);

  const selectedDataSource = dataSources.find((ds) => ds.data_source_id === selectedDataSourceId) || (dataSources.length > 0 ? dataSources[0] : null);

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
