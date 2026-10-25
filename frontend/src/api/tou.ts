import client from './client';

export interface TouSummary {
    version: string;
    months: { [key: string]: string[] }; // key is month "1"-"12", value is array of 96 strings
    coefficients: { [key: string]: number };
}

export const getTouVersions = async (): Promise<string[]> => {
    const response = await client.get<string[]>('/api/v1/tou-rules/versions');
    return response.data;
};

export const getTouSummary = async (version: string): Promise<TouSummary> => {
    const response = await client.get<TouSummary>('/api/v1/tou-rules/summary', {
        params: { version }
    });
    return response.data;
};
