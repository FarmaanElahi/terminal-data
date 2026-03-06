/**
 * Custom TradingView charting library indicators.
 *
 * Smart Candle Classifier – colors bars by volume/ADR criteria + EMA crossover.
 *
 * Conditions (priority high → low):
 *   1. High Vol Bullish   – vol ≥ mult_high × avg_vol  AND  close > open  AND  body ≥ adr_mult_strong × ADR
 *   2. High Vol Bearish   – vol ≥ mult_high × avg_vol  AND  close < open  AND  body ≥ adr_mult_strong × ADR
 *   3. Above Avg Vol Move – vol ≥ avg_vol              AND  body ≥ adr_mult_moderate × ADR (any direction)
 *   4. Price Close Above EMA – close crosses above EMA(ema_period)  (lowest priority)
 *
 * Colors are configurable in two places:
 *  • Settings tab (Inputs) – color pickers organised by group (this file)
 *  • Style tab              – palette entry colours that actually drive bar rendering
 * Both default to the same values.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── Palette indices ────────────────────────────────────────────────────────
const IDX = { HIGH_BULL: 0, HIGH_BEAR: 1, AVG_MOVE: 2, EMA_UP: 3 } as const;

// ─── Default colors ─────────────────────────────────────────────────────────
const DEF_COLOR_HIGH_BULL = "#0D47A1"; // Deep Blue
const DEF_COLOR_HIGH_BEAR = "#4E342E"; // Dark Brown
const DEF_COLOR_AVG_MOVE = "#82B1FF"; // Light Blue
const DEF_COLOR_EMA_UP = "#B9F6CA"; // Light Green

export function getCustomIndicators(PineJS: any): Promise<any[]> {
  return Promise.resolve([buildCandleClassifier(PineJS), buildRMV(PineJS)]);
}

// ─── Smart Candle Classifier ─────────────────────────────────────────────────

function buildCandleClassifier(PineJS: any): any {
  return {
    name: "Smart Candle Classifier",
    metainfo: {
      _metainfoVersion: 51,
      id: "SmartCandleClassifier@tv-basicstudies-1",
      description: "Smart Candle Classifier",
      shortDescription: "Smart Candle",
      is_price_study: true,
      isCustomIndicator: true,
      format: { type: "inherit" },

      // ── Bar colorer (actual rendering) ──────────────────────────────
      plots: [{ id: "plot_bar", type: "bar_colorer", palette: "barPalette" }],

      palettes: {
        barPalette: {
          colors: [
            { name: "High Vol Bullish" },
            { name: "High Vol Bearish" },
            { name: "Above Avg Vol Move" },
            { name: "Price Close Above EMA" },
          ],
          valToIndex: {
            [IDX.HIGH_BULL]: IDX.HIGH_BULL,
            [IDX.HIGH_BEAR]: IDX.HIGH_BEAR,
            [IDX.AVG_MOVE]: IDX.AVG_MOVE,
            [IDX.EMA_UP]: IDX.EMA_UP,
          },
        },
      },

      defaults: {
        // Style-tab palette colours (must match the color-input defaults below)
        palettes: {
          barPalette: {
            colors: [
              { color: DEF_COLOR_HIGH_BULL, width: 1, style: 0 },
              { color: DEF_COLOR_HIGH_BEAR, width: 1, style: 0 },
              { color: DEF_COLOR_AVG_MOVE, width: 1, style: 0 },
              { color: DEF_COLOR_EMA_UP, width: 1, style: 0 },
            ],
          },
        },

        // Settings-tab input defaults
        inputs: {
          // ── Group: High Volume ──────────────────────────────────────
          vol_period: 20,
          vol_mult: 1.5,
          adr_period: 20,
          adr_mult_strong: 1.2,
          color_high_bull: DEF_COLOR_HIGH_BULL,
          color_high_bear: DEF_COLOR_HIGH_BEAR,
          // ── Group: Above Avg Volume ─────────────────────────────────
          adr_mult_moderate: 1.1,
          color_avg_move: DEF_COLOR_AVG_MOVE,
          // ── Group: Price Close Above EMA ────────────────────────────
          ema_period: 10,
          color_ema_up: DEF_COLOR_EMA_UP,
        },
      },

      styles: {},

      // ── Inputs (Settings tab) ──────────────────────────────────────
      inputs: [
        // ── Group: High Volume ──────────────────────────────────────
        {
          id: "vol_period",
          name: "Volume Avg Period",
          defval: 20,
          type: "integer",
          min: 1,
          max: 500,
          group: "High Volume",
        },
        {
          id: "vol_mult",
          name: "Volume Multiplier",
          defval: 1.5,
          type: "float",
          min: 1.0,
          max: 20.0,
          step: 0.1,
          group: "High Volume",
          tooltip: "Bar is colored when volume ≥ this multiple of the avg",
        },
        {
          id: "adr_period",
          name: "ADR Period",
          defval: 20,
          type: "integer",
          min: 1,
          max: 500,
          group: "High Volume",
        },
        {
          id: "adr_mult_strong",
          name: "ADR Multiplier (Strong Move)",
          defval: 1.2,
          type: "float",
          min: 0.1,
          max: 20.0,
          step: 0.1,
          group: "High Volume",
          tooltip: "Candle body must be ≥ this multiple of ADR",
        },
        {
          id: "color_high_bull",
          name: "Bullish Color",
          defval: DEF_COLOR_HIGH_BULL,
          type: "color",
          group: "High Volume",
        },
        {
          id: "color_high_bear",
          name: "Bearish Color",
          defval: DEF_COLOR_HIGH_BEAR,
          type: "color",
          group: "High Volume",
        },

        // ── Group: Above Avg Volume ─────────────────────────────────
        {
          id: "adr_mult_moderate",
          name: "ADR Multiplier (Moderate Move)",
          defval: 1.1,
          type: "float",
          min: 0.1,
          max: 20.0,
          step: 0.1,
          group: "Above Avg Volume",
          tooltip: "Candle body must be ≥ this multiple of ADR",
        },
        {
          id: "color_avg_move",
          name: "Color",
          defval: DEF_COLOR_AVG_MOVE,
          type: "color",
          group: "Above Avg Volume",
        },

        // ── Group: Price Close Above EMA ────────────────────────────
        {
          id: "ema_period",
          name: "EMA Period",
          defval: 10,
          type: "integer",
          min: 1,
          max: 500,
          group: "Price Close Above EMA",
        },
        {
          id: "color_ema_up",
          name: "Color",
          defval: DEF_COLOR_EMA_UP,
          type: "color",
          group: "Price Close Above EMA",
        },
      ],
    },

    constructor: function (this: any) {
      this.main = function (ctx: any, inputs: any) {
        this._context = ctx;
        this._input = inputs;

        // ── Read inputs (order matches the inputs array above) ──────
        const volPeriod: number = this._input(0); // vol_period
        const volMult: number = this._input(1); // vol_mult
        const adrPeriod: number = this._input(2); // adr_period
        const adrMultStrong: number = this._input(3); // adr_mult_strong
        // inputs 4 & 5 → color_high_bull, color_high_bear (not used in calc)
        const adrMultMod: number = this._input(6); // adr_mult_moderate
        // input 7 → color_avg_move (not used in calc)
        const emaPeriod: number = this._input(8); // ema_period
        // input 9 → color_ema_up (not used in calc)

        // ── Raw bar values ──────────────────────────────────────────
        const close: number = PineJS.Std.close(this._context);
        const open: number = PineJS.Std.open(this._context);
        const high: number = PineJS.Std.high(this._context);
        const low: number = PineJS.Std.low(this._context);
        const vol: number = PineJS.Std.volume(this._context);

        // ── Persistent series – order must never change between bars ──
        const closeS = this._context.new_var(close); // #1
        const volS = this._context.new_var(vol); // #2
        const rangeS = this._context.new_var(high - low); // #3

        // ── Rolling averages ────────────────────────────────────────
        const avgVol: number = PineJS.Std.sma(volS, volPeriod, this._context);
        const adr: number = PineJS.Std.sma(rangeS, adrPeriod, this._context);
        const ema: number = PineJS.Std.ema(closeS, emaPeriod, this._context);

        const emaS = this._context.new_var(ema); // #4

        // ── Warm-up: skip bars before averages are available ────────
        if (isNaN(avgVol) || isNaN(adr) || isNaN(ema)) return [NaN];

        const body = Math.abs(close - open);
        const isBull = close > open;
        const isBear = close < open;
        const prevClose: number = closeS.get(1);
        const prevEma: number = emaS.get(1);

        // ── Priority 1: High Vol Bullish (Deep Blue) ────────────────
        if (vol >= volMult * avgVol && isBull && body >= adrMultStrong * adr) {
          return [IDX.HIGH_BULL];
        }

        // ── Priority 2: High Vol Bearish (Dark Brown) ───────────────
        if (vol >= volMult * avgVol && isBear && body >= adrMultStrong * adr) {
          return [IDX.HIGH_BEAR];
        }

        // ── Priority 3: Above Avg Vol + Moderate Move (Light Blue) ──
        if (vol >= avgVol && body >= adrMultMod * adr) {
          return [IDX.AVG_MOVE];
        }

        // ── Priority 4: Price Close Above EMA (Light Green) ─────────
        if (
          !isNaN(prevClose) &&
          !isNaN(prevEma) &&
          close > ema &&
          prevClose <= prevEma
        ) {
          return [IDX.EMA_UP];
        }

        return [NaN]; // no condition met → default bar color
      };
    },
  };
}

// ─── RMV (Relative Momentum Volatility) ────────────────────────────────

const DEF_RMV_COLOR = "#F59E0B"; // Amber

function buildRMV(PineJS: any): any {
  return {
    name: "RMV",
    metainfo: {
      _metainfoVersion: 51,
      id: "RMV@tv-basicstudies-1",
      description: "RMV",
      shortDescription: "RMV",
      is_price_study: false,
      isCustomIndicator: true,
      format: { type: "percent", precision: 2 },

      plots: [{ id: "plot_0", type: "line" }],

      defaults: {
        styles: {
          plot_0: {
            linestyle: 0,
            visible: true,
            linewidth: 2,
            plottype: 2,
            trackPrice: false,
            color: DEF_RMV_COLOR,
          },
        },
        inputs: {
          loopback: 20,
        },
      },

      styles: {
        plot_0: {
          title: "RMV",
          histogramBase: 0,
        },
      },

      inputs: [
        {
          id: "loopback",
          name: "Loopback",
          defval: 20,
          type: "integer",
          min: 2,
          max: 500,
        },
      ],
    },

    constructor: function (this: any) {
      this.main = function (ctx: any, inputs: any) {
        this._context = ctx;
        this._input = inputs;

        this._context.select_sym(0);

        const loopback: number = this._input(0);

        const high: number = PineJS.Std.high(this._context);
        const low: number = PineJS.Std.low(this._context);
        const close: number = PineJS.Std.close(this._context);

        // Persistent series (order must stay stable)
        const highS = this._context.new_var(high); // #1
        const lowS = this._context.new_var(low); // #2
        const closeS = this._context.new_var(close); // #3

        // === 2-period Calculations ===
        const high2 = PineJS.Std.highest(highS, 2, this._context);
        const lowOfHigh2 = PineJS.Std.lowest(highS, 2, this._context);
        const close2 = PineJS.Std.highest(closeS, 2, this._context);
        const lowClose2 = PineJS.Std.lowest(closeS, 2, this._context);
        const highOfLow2 = PineJS.Std.highest(lowS, 2, this._context);
        const low2 = PineJS.Std.lowest(lowS, 2, this._context);

        const invalid2p =
          !isFinite(lowClose2) || lowClose2 === 0 || !isFinite(low2) || low2 === 0;

        const term1_2p = invalid2p
          ? NaN
          : ((high2 - lowOfHigh2) / lowClose2) * 100;
        const term2_2p = invalid2p
          ? NaN
          : ((close2 - lowClose2) / lowClose2) * 100;
        const term3_2p = invalid2p
          ? NaN
          : ((highOfLow2 - low2) / low2) * 100;
        const avg_2p = (term1_2p + 1.5 * term2_2p + term3_2p) / 3;

        // === 3-period Calculations ===
        const high3 = PineJS.Std.highest(highS, 3, this._context);
        const lowOfHigh3 = PineJS.Std.lowest(highS, 3, this._context);
        const close3 = PineJS.Std.highest(closeS, 3, this._context);
        const lowClose3 = PineJS.Std.lowest(closeS, 3, this._context);

        const invalid3p = !isFinite(lowClose3) || lowClose3 === 0;

        const term1_3p = invalid3p
          ? NaN
          : ((high3 - lowOfHigh3) / lowClose3) * 100;
        const term2_3p = invalid3p
          ? NaN
          : 1.5 * ((close3 - lowClose3) / lowClose3) * 100;
        const avg_3p = (term1_3p + term2_3p) / 2;

        // === Combine Averages ===
        const combinedAvg = (3 * avg_2p + avg_3p) / 4;

        // Persistent series for rolling normalization
        const combinedS = this._context.new_var(combinedAvg); // #4

        // === Normalization over loopback ===
        const highestCombined = PineJS.Std.highest(
          combinedS,
          loopback,
          this._context,
        );
        const lowestCombined = PineJS.Std.lowest(
          combinedS,
          loopback,
          this._context,
        );

        const denom = highestCombined - lowestCombined;
        if (!isFinite(denom) || denom === 0) return [NaN];

        const normalizedScore =
          ((combinedAvg - lowestCombined) / denom) * 100;

        return [normalizedScore];
      };
    },
  };
}
