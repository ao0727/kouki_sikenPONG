#ifndef BALL_H
#define BALL_H

#include "DxLib.h"
#include "Paddle.h"
#include "Score.h"  
class Ball {
private:
    int x, y;       // ボールの位置
    int speedX, speedY;  // ボールの速度
    int size;       // ボールのサイズ
    Score& score;   // Score クラスの参照

public:
    
    Ball(int startX, int startY, Score& scoreRef);

    // ボールの更新
    void Update();

    // ボールの描画
    void Draw() const;

    // パドルとの衝突処理
    void CheckCollision(Paddle& player, Paddle& cpu);

    // ボールのリセット
    void Reset(int startX, int startY);

    // ボールのY座標を取得
    int GetY() const { return y; }
};

#endif // BALL_H
