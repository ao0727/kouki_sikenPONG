#ifndef SCORE_H
#define SCORE_H

#include "DxLib.h"

class Score {
private:
    int playerScore; // プレイヤーのスコア
    int cpuScore;    // CPUのスコア
    const int winScore = 11; // 勝利条件のスコア

public:
    // コンストラクタ
    Score();

    // スコアの更新
    void AddPlayerScore();
    void AddCpuScore();

    // スコアの描画
    void Draw() const;

    // ゲーム終了条件の判定
    bool IsGameOver() const;

    // スコアをリセット
    void Reset();
};

#endif // SCORE_H
