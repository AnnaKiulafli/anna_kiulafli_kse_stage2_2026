# Project reflection

What went wrong? My first approach treated the dataset too simply: I underestimated timezone conversion, mixed administrative levels too easily, and initially relied on paths that depended on the current working directory. How did I adjust? I separated raion-level analysis from oblast and non-raion records, excluded the current partial day, corrected path handling, added tests, and reviewed each change through pull requests before merging. Why is the final version better? It is now reproducible, methodologically clearer, and more transparent about limitations. The final pipeline uses leakage-free walk-forward baselines, documents every major decision, and avoids presenting recorded alert data as attacks or operational forecasts.

