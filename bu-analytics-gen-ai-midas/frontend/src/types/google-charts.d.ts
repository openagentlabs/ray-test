declare module 'google-charts' {
  export class Chart {
    constructor(element: HTMLElement);
    draw(data: any, options: any): void;
  }
}

declare global {
  interface Window {
    google: {
      charts: {
        load: (version: string, options: any) => void;
        setOnLoadCallback: (callback: () => void) => void;
      };
      visualization: {
        arrayToDataTable: (data: any[][]) => any;
        LineChart: any;
        BarChart: any;
        PieChart: any;
        AreaChart: any;
        ColumnChart: any;
        ScatterChart: any;
        Table: any;
      };
    };
  }
} 