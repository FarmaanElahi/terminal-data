/**
 * Custom TradingView charting library indicators.
 *
 * Smart Candle Classifier:
 * Mirrors the provided Pine Script bar-color logic (expansion, contraction,
 * EMA bounce, and EMA crossover marker).
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── Palette indices ────────────────────────────────────────────────────────
const IDX = {
  GREAT_EXPANSION: 0,
  DECENT_EXPANSION: 1,
  HIGH_DAILY_CHANGE: 2,
  EMA_BOUNCE: 3,
  RMV_CONTRACTION: 4,
  POOR_CONTRACTION: 5,
} as const;

// ─── Default colors ─────────────────────────────────────────────────────────
const DEF_COLOR_GREAT_EXPANSION = "#0000FF"; // color.rgb(0, 0, 255)
const DEF_COLOR_DECENT_EXPANSION = "#2196F3"; // color.rgb(33, 150, 243)
const DEF_COLOR_HIGH_DAILY_CHANGE = "#9333EA"; // Purple
const DEF_COLOR_EMA_BOUNCE = "#4D9650"; // color.rgb(77, 150, 80)
const DEF_COLOR_RMV_CONTRACTION = "#787B86"; // TradingView color.gray
const DEF_COLOR_POOR_CONTRACTION = "#550E0E"; // color.rgb(85, 14, 14)
const DEF_COLOR_EMA_CROSS = "#FFFFFF";

export function getCustomIndicators(PineJS: any): Promise<any[]> {
  return Promise.resolve([buildCandleClassifier(PineJS), buildRMV(PineJS)]);
}

function computeRmvScore(
  PineJS: any,
  context: any,
  highS: any,
  lowS: any,
  closeS: any,
  loopback: number,
): number {
  const high2 = PineJS.Std.highest(highS, 2, context);
  const lowOfHigh2 = PineJS.Std.lowest(highS, 2, context);
  const close2 = PineJS.Std.highest(closeS, 2, context);
  const lowClose2 = PineJS.Std.lowest(closeS, 2, context);
  const highOfLow2 = PineJS.Std.highest(lowS, 2, context);
  const low2 = PineJS.Std.lowest(lowS, 2, context);

  const invalid2p =
    !Number.isFinite(lowClose2) ||
    lowClose2 === 0 ||
    !Number.isFinite(low2) ||
    low2 === 0;
  const term1_2p = invalid2p ? NaN : ((high2 - lowOfHigh2) / lowClose2) * 100;
  const term2_2p = invalid2p ? NaN : ((close2 - lowClose2) / lowClose2) * 100;
  const term3_2p = invalid2p ? NaN : ((highOfLow2 - low2) / low2) * 100;
  const avg2p = (term1_2p + 1.5 * term2_2p + term3_2p) / 3;

  const high3 = PineJS.Std.highest(highS, 3, context);
  const lowOfHigh3 = PineJS.Std.lowest(highS, 3, context);
  const close3 = PineJS.Std.highest(closeS, 3, context);
  const lowClose3 = PineJS.Std.lowest(closeS, 3, context);

  const invalid3p = !Number.isFinite(lowClose3) || lowClose3 === 0;
  const term1_3p = invalid3p ? NaN : ((high3 - lowOfHigh3) / lowClose3) * 100;
  const term2_3p = invalid3p ? NaN : 1.5 * ((close3 - lowClose3) / lowClose3) * 100;
  const avg3p = (term1_3p + term2_3p) / 2;

  const combinedAvg = (3 * avg2p + avg3p) / 4;
  const combinedS = context.new_var(combinedAvg);
  const highestCombined = PineJS.Std.highest(combinedS, loopback, context);
  const lowestCombined = PineJS.Std.lowest(combinedS, loopback, context);

  const denom = highestCombined - lowestCombined;
  if (!Number.isFinite(denom) || denom === 0) return NaN;

  return ((combinedAvg - lowestCombined) / denom) * 100;
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
      linkedToSeries: true,
      isCustomIndicator: true,
      format: { type: "inherit" },

      plots: [
        { id: "plot_bar", type: "bar_colorer", palette: "barPalette" },
        { id: "plot_ema_cross", type: "shapes" },
      ],

      palettes: {
        barPalette: {
          colors: [
            { name: "Great Expansion" },
            { name: "Decent Expansion" },
            { name: "High Daily Change" },
            { name: "EMA Bounce" },
            { name: "RMV Contraction" },
            { name: "Poor Contraction" },
          ],
          valToIndex: {
            [IDX.GREAT_EXPANSION]: IDX.GREAT_EXPANSION,
            [IDX.DECENT_EXPANSION]: IDX.DECENT_EXPANSION,
            [IDX.HIGH_DAILY_CHANGE]: IDX.HIGH_DAILY_CHANGE,
            [IDX.EMA_BOUNCE]: IDX.EMA_BOUNCE,
            [IDX.RMV_CONTRACTION]: IDX.RMV_CONTRACTION,
            [IDX.POOR_CONTRACTION]: IDX.POOR_CONTRACTION,
          },
        },
      },

      defaults: {
        palettes: {
          barPalette: {
            colors: [
              { color: DEF_COLOR_GREAT_EXPANSION, width: 1, style: 0 },
              { color: DEF_COLOR_DECENT_EXPANSION, width: 1, style: 0 },
              { color: DEF_COLOR_HIGH_DAILY_CHANGE, width: 1, style: 0 },
              { color: DEF_COLOR_EMA_BOUNCE, width: 1, style: 0 },
              { color: DEF_COLOR_RMV_CONTRACTION, width: 1, style: 0 },
              { color: DEF_COLOR_POOR_CONTRACTION, width: 1, style: 0 },
            ],
          },
        },
        styles: {
          plot_ema_cross: {
            color: DEF_COLOR_EMA_CROSS,
            textColor: DEF_COLOR_EMA_CROSS,
            plottype: "shape_circle",
            location: "Absolute",
            visible: true,
            size: "tiny",
          },
        },
        inputs: {
          price_action_color_contraction_enable: true,
          rmv_loopback: 14,
          rmv_min: 0,
          rmv_enable_indices: false,
          enable_expansion: true,
          enable_contraction: true,
          enable_ema_bounce: true,
          enable_ema_cross_over: true,
          enable_high_daily_change: true,
          high_daily_change_threshold: 4.0,
        },
      },

      styles: {
        plot_ema_cross: {
          title: "EMA Cross",
          text: "",
          location: "Absolute",
          plottype: "shape_circle",
        },
      },

      inputs: [
        {
          id: "price_action_color_contraction_enable",
          name: "Tightness",
          defval: true,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "rmv_loopback",
          name: "Contraction Check Loopback",
          defval: 14,
          type: "integer",
          min: 2,
          max: 500,
          group: "Price Volume Action Coloring",
        },
        {
          id: "rmv_min",
          name: "Contraction Check Threshold",
          defval: 0,
          type: "float",
          min: -100.0,
          max: 100.0,
          step: 0.1,
          group: "Price Volume Action Coloring",
        },
        {
          id: "rmv_enable_indices",
          name: "Contraction enabled for indices",
          defval: false,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "enable_expansion",
          name: "Expansion",
          defval: true,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "enable_contraction",
          name: "Contraction",
          defval: true,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "enable_ema_bounce",
          name: "MA Bounce",
          defval: true,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "enable_ema_cross_over",
          name: "MA Cross Over",
          defval: true,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "enable_high_daily_change",
          name: "High Daily Change",
          defval: true,
          type: "bool",
          group: "Price Volume Action Coloring",
        },
        {
          id: "high_daily_change_threshold",
          name: "High Daily Change Threshold (%)",
          defval: 4.0,
          type: "float",
          min: 0.0,
          max: 100.0,
          step: 0.1,
          group: "Price Volume Action Coloring",
        },
      ],
    },

    constructor: function (this: any) {
      this.main = function (ctx: any, inputs: any) {
        this._context = ctx;
        this._input = inputs;

        const tightnessEnabled: boolean = this._input(0);
        const rmvLoopback: number = this._input(1);
        const rmvMin: number = this._input(2);
        const rmvEnableIndices: boolean = this._input(3);
        const enableExpansion: boolean = this._input(4);
        const enableContraction: boolean = this._input(5);
        const enableEmaBounce: boolean = this._input(6);
        const enableEmaCrossOver: boolean = this._input(7);
        const enableHighDailyChange: boolean = this._input(8);
        const highDailyChangeThreshold: number = this._input(9);

        const close: number = PineJS.Std.close(this._context);
        const open: number = PineJS.Std.open(this._context);
        const high: number = PineJS.Std.high(this._context);
        const low: number = PineJS.Std.low(this._context);
        const vol: number = PineJS.Std.volume(this._context);

        const highS = this._context.new_var(high);
        const lowS = this._context.new_var(low);
        const closeS = this._context.new_var(close);
        const volS = this._context.new_var(vol);
        const prevClose: number = closeS.get(1);
        const chg =
          Number.isFinite(prevClose) && prevClose !== 0
            ? ((close - prevClose) / prevClose) * 100
            : NaN;

        const ema10 = PineJS.Std.ema(closeS, 10, this._context);
        const ema20 = PineJS.Std.ema(closeS, 20, this._context);
        const ema50 = PineJS.Std.ema(closeS, 50, this._context);
        const ema10S = this._context.new_var(ema10);
        const ema20S = this._context.new_var(ema20);
        const ema50S = this._context.new_var(ema50);

        const atr14 = PineJS.Std.atr(14, this._context);
        const atrPct =
          Number.isFinite(atr14) && close !== 0 ? (atr14 / close) * 100 : NaN;
        const avgVol = PineJS.Std.sma(volS, 20, this._context);
        const aboveAvgVol = Number.isFinite(avgVol) && vol > avgVol;

        const isDecentExpansion =
          Number.isFinite(chg) &&
          Number.isFinite(atrPct) &&
          chg > atrPct &&
          aboveAvgVol;
        const isGreatExpansion =
          isDecentExpansion && Number.isFinite(avgVol) && vol > avgVol * 1.5;
        const isPoorContraction =
          Number.isFinite(chg) &&
          Number.isFinite(atrPct) &&
          chg < 0 &&
          Math.abs(chg) > atrPct * 1.1 &&
          aboveAvgVol;

        const lowPrev = lowS.get(1);
        const ema10Prev = ema10S.get(1);
        const ema20Prev = ema20S.get(1);
        const ema50Prev = ema50S.get(1);
        const bounce10 =
          Number.isFinite(lowPrev) &&
          Number.isFinite(ema10Prev) &&
          Number.isFinite(ema10) &&
          lowPrev < ema10Prev &&
          low <= ema10 &&
          close > ema10 &&
          close > open;
        const bounce20 =
          Number.isFinite(lowPrev) &&
          Number.isFinite(ema20Prev) &&
          Number.isFinite(ema20) &&
          lowPrev < ema20Prev &&
          low <= ema20 &&
          close > ema20 &&
          close > open;
        const bounce50 =
          Number.isFinite(lowPrev) &&
          Number.isFinite(ema50Prev) &&
          Number.isFinite(ema50) &&
          lowPrev < ema50Prev &&
          low <= ema50 &&
          close > ema50 &&
          close > open;

        const rmvEval = computeRmvScore(
          PineJS,
          this._context,
          highS,
          lowS,
          closeS,
          rmvLoopback,
        );

        const symbolType = String(this._context?.symbol?.info?.type ?? "").toLowerCase();
        const contractionAllowedForSymbol =
          symbolType === "index" ? rmvEnableIndices : true;

        const period = String(this._context?.symbol?.period ?? "").toUpperCase();
        const isDailyTimeframe = period === "D" || period === "1D";
        const isHighDailyChange =
          enableHighDailyChange &&
          isDailyTimeframe &&
          Number.isFinite(chg) &&
          chg > highDailyChangeThreshold;

        let barColor = NaN;
        if (enableExpansion && isGreatExpansion) {
          barColor = IDX.GREAT_EXPANSION;
        } else if (enableExpansion && isDecentExpansion) {
          barColor = IDX.DECENT_EXPANSION;
        } else if (isHighDailyChange) {
          barColor = IDX.HIGH_DAILY_CHANGE;
        } else if (enableEmaBounce && (bounce10 || bounce20 || bounce50) && aboveAvgVol) {
          barColor = IDX.EMA_BOUNCE;
        } else if (
          contractionAllowedForSymbol &&
          tightnessEnabled &&
          Number.isFinite(rmvEval) &&
          rmvEval <= rmvMin
        ) {
          barColor = IDX.RMV_CONTRACTION;
        } else if (enableContraction && isPoorContraction) {
          barColor = IDX.POOR_CONTRACTION;
        }

        const emaCross1 =
          Number.isFinite(ema10) &&
          Number.isFinite(ema20) &&
          Number.isFinite(ema10Prev) &&
          Number.isFinite(ema20Prev) &&
          ema10 > ema20 &&
          ema10Prev <= ema20Prev;
        const emaCross2 =
          Number.isFinite(ema10) &&
          Number.isFinite(ema50) &&
          Number.isFinite(ema10Prev) &&
          Number.isFinite(ema50Prev) &&
          ema10 > ema50 &&
          ema10Prev <= ema50Prev;
        const emaCrossValue =
          enableEmaCrossOver && (emaCross1 || emaCross2) ? ema10 : NaN;

        return [barColor, emaCrossValue];
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
        const highS = this._context.new_var(high);
        const lowS = this._context.new_var(low);
        const closeS = this._context.new_var(close);

        return [
          computeRmvScore(
            PineJS,
            this._context,
            highS,
            lowS,
            closeS,
            loopback,
          ),
        ];
      };
    },
  };
}
