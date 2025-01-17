#ifndef PADDLE_H
#define PADDLE_H

#include "DxLib.h"
//#include "Ball.h"  // Ball クラスのインクルード

class Ball;

class Paddle {
private:
    int x, y;       // パドルの位置
    int width, height;  // パドルのサイズ
    int speed;      // パドルの移動速度

public:
   
    Paddle(int startX, int startY);

    // プレイヤーの操作
    void Update(int upKey, int downKey);

    // CPUの操作
    void AIControl( const Ball& ball);  

    // パドルの描画
    void Draw() const;

    // パドルの位置情報
    int GetX() const;
    int GetY() const;
    int GetWidth() const;
    int GetHeight() const;
};

#endif // PADDLE_H
